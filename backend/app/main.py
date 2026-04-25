from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .models import ProjectMetadata, ProjectStatus, ProjectSummary, ReconstructionOptions
from .pipeline import run_reconstruction
from .storage import (
    create_project,
    ensure_data_dirs,
    import_image_folder,
    list_projects,
    load_metadata,
    read_log,
    save_metadata,
    save_uploads,
)


ensure_data_dirs()

app = FastAPI(title="Substation Twin Reconstruction API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/data", StaticFiles(directory=settings.data_dir), name="data")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_dir": str(settings.data_dir)}


@app.get("/api/projects", response_model=list[ProjectSummary])
def projects() -> list[ProjectSummary]:
    return list_projects()


@app.get("/api/projects/{project_id}", response_model=ProjectMetadata)
def project(project_id: str) -> ProjectMetadata:
    try:
        return load_metadata(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.get("/api/projects/{project_id}/logs")
def logs(project_id: str) -> dict[str, str]:
    try:
        return {"logs": read_log(project_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.post("/api/projects", response_model=ProjectMetadata)
async def create_reconstruction_project(
    background_tasks: BackgroundTasks,
    name: Annotated[str, Form()] = "substation-scene",
    files: Annotated[list[UploadFile], File()] = [],
    method: Annotated[str, Form()] = settings.default_method,
    max_num_iterations: Annotated[int, Form()] = settings.default_iterations,
    gpu_ids: Annotated[str | None, Form()] = None,
    matching_method: Annotated[str, Form()] = "exhaustive",
    high_quality: Annotated[bool, Form()] = True,
) -> ProjectMetadata:
    metadata = create_project(name=name)
    count = await save_uploads(metadata.id, files)
    if count < 3:
        raise HTTPException(status_code=400, detail="Upload at least 3 images.")

    options = ReconstructionOptions(
        method=method,
        max_num_iterations=max_num_iterations,
        gpu_ids=gpu_ids,
        matching_method=matching_method,
        high_quality=high_quality,
    )
    metadata.options = options
    metadata.status = ProjectStatus.queued
    save_metadata(metadata)
    background_tasks.add_task(run_reconstruction, metadata.id, options)
    return load_metadata(metadata.id)


@app.post("/api/projects/import-folder", response_model=ProjectMetadata)
def import_folder_project(
    background_tasks: BackgroundTasks,
    name: Annotated[str, Form()] = "substation-scene",
    folder_path: Annotated[str, Form()] = "",
    import_mode: Annotated[str, Form()] = "symlink",
    autorun: Annotated[bool, Form()] = True,
    method: Annotated[str, Form()] = settings.default_method,
    max_num_iterations: Annotated[int, Form()] = settings.default_iterations,
    gpu_ids: Annotated[str | None, Form()] = None,
    matching_method: Annotated[str, Form()] = "exhaustive",
    high_quality: Annotated[bool, Form()] = True,
) -> ProjectMetadata:
    if not settings.allow_local_import:
        raise HTTPException(
            status_code=403,
            detail="Local folder import is disabled. Set SUBTWIN_ALLOW_LOCAL_IMPORT=1.",
        )

    metadata = create_project(name=name)
    try:
        count = import_image_folder(metadata.id, Path(folder_path), mode=import_mode)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if count < 3:
        raise HTTPException(status_code=400, detail="Import at least 3 images.")

    options = ReconstructionOptions(
        method=method,
        max_num_iterations=max_num_iterations,
        gpu_ids=gpu_ids,
        matching_method=matching_method,
        high_quality=high_quality,
    )
    metadata = load_metadata(metadata.id)
    metadata.options = options
    metadata.status = ProjectStatus.queued if autorun else ProjectStatus.created
    save_metadata(metadata)

    if autorun:
        background_tasks.add_task(run_reconstruction, metadata.id, options)
    return load_metadata(metadata.id)


@app.post("/api/projects/{project_id}/rerun", response_model=ProjectMetadata)
def rerun_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    method: Annotated[str, Form()] = settings.default_method,
    max_num_iterations: Annotated[int, Form()] = settings.default_iterations,
    gpu_ids: Annotated[str | None, Form()] = None,
    matching_method: Annotated[str, Form()] = "exhaustive",
    high_quality: Annotated[bool, Form()] = True,
) -> ProjectMetadata:
    try:
        metadata = load_metadata(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

    options = ReconstructionOptions(
        method=method,
        max_num_iterations=max_num_iterations,
        gpu_ids=gpu_ids,
        matching_method=matching_method,
        high_quality=high_quality,
    )
    metadata.status = ProjectStatus.queued
    metadata.options = options
    metadata.error = None
    save_metadata(metadata)
    background_tasks.add_task(run_reconstruction, project_id, options)
    return load_metadata(project_id)
