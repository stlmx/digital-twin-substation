from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from fastapi import UploadFile

from .config import settings
from .models import ProjectMetadata, ProjectSummary, ProjectStatus


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def is_supported_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and not path.name.startswith(".")
        and not path.name.startswith("._")
    )


def ensure_data_dirs() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    projects_dir().mkdir(parents=True, exist_ok=True)


def projects_dir() -> Path:
    return settings.data_dir / "projects"


def project_dir(project_id: str) -> Path:
    return projects_dir() / project_id


def images_dir(project_id: str) -> Path:
    return project_dir(project_id) / "images"


def nerfstudio_data_dir(project_id: str) -> Path:
    return project_dir(project_id) / "nerfstudio-data"


def outputs_dir(project_id: str) -> Path:
    return project_dir(project_id) / "outputs"


def exports_dir(project_id: str) -> Path:
    return project_dir(project_id) / "exports"


def logs_path(project_id: str) -> Path:
    return project_dir(project_id) / "pipeline.log"


def metadata_path(project_id: str) -> Path:
    return project_dir(project_id) / "metadata.json"


def new_project_id() -> str:
    return uuid.uuid4().hex[:12]


def create_project(name: str) -> ProjectMetadata:
    ensure_data_dirs()
    project_id = new_project_id()
    project_dir(project_id).mkdir(parents=True)
    images_dir(project_id).mkdir()
    metadata = ProjectMetadata(id=project_id, name=name)
    save_metadata(metadata)
    logs_path(project_id).write_text("", encoding="utf-8")
    return metadata


def save_metadata(metadata: ProjectMetadata) -> None:
    metadata.updated_at = datetime.now(timezone.utc).isoformat()
    path = metadata_path(metadata.id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)


def refresh_image_count(project_id: str) -> int:
    count = sum(
        1
        for path in images_dir(project_id).iterdir()
        if is_supported_image(path)
    )
    meta = load_metadata(project_id)
    meta.image_count = count
    save_metadata(meta)
    return count


def load_metadata(project_id: str) -> ProjectMetadata:
    raw = metadata_path(project_id).read_text(encoding="utf-8")
    return ProjectMetadata.model_validate_json(raw)


def list_projects() -> list[ProjectSummary]:
    ensure_data_dirs()
    items: list[ProjectSummary] = []
    for path in sorted(projects_dir().glob("*/metadata.json"), reverse=True):
        try:
            meta = ProjectMetadata.model_validate_json(path.read_text(encoding="utf-8"))
            items.append(ProjectSummary(**meta.model_dump()))
        except (json.JSONDecodeError, ValueError):
            continue
    return sorted(items, key=lambda item: item.updated_at, reverse=True)


def append_log(project_id: str, line: str) -> None:
    with logs_path(project_id).open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip() + "\n")


def read_log(project_id: str) -> str:
    path = logs_path(project_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def set_status(
    project_id: str,
    status: ProjectStatus,
    *,
    error: str | None = None,
    artifacts: dict | None = None,
) -> ProjectMetadata:
    meta = load_metadata(project_id)
    meta.status = status
    meta.error = error
    if artifacts is not None:
        meta.artifacts.update(artifacts)
    save_metadata(meta)
    return meta


async def save_uploads(project_id: str, files: Iterable["UploadFile"]) -> int:
    count = 0
    destination = images_dir(project_id)
    destination.mkdir(parents=True, exist_ok=True)

    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in IMAGE_EXTENSIONS or Path(upload.filename or "").name.startswith("."):
            continue
        safe_name = f"{count:05d}{suffix}"
        with (destination / safe_name).open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        count += 1

    meta = load_metadata(project_id)
    meta.image_count = count
    save_metadata(meta)
    return count


def import_image_folder(project_id: str, source: Path, *, mode: str = "symlink") -> int:
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Image folder not found: {source}")
    if mode not in {"symlink", "copy"}:
        raise ValueError("mode must be 'symlink' or 'copy'")

    destination = images_dir(project_id)
    destination.mkdir(parents=True, exist_ok=True)
    image_paths = [
        path
        for path in sorted(source.iterdir())
        if is_supported_image(path)
    ]

    for index, path in enumerate(image_paths):
        target = destination / f"{index:05d}{path.suffix.lower()}"
        if target.exists() or target.is_symlink():
            target.unlink()
        if mode == "symlink":
            target.symlink_to(path.resolve())
        else:
            shutil.copy2(path, target)

    meta = load_metadata(project_id)
    meta.image_count = len(image_paths)
    save_metadata(meta)
    return len(image_paths)
