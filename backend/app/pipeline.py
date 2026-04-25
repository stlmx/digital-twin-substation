from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import settings
from .colmap import colmap_points_to_ply
from .models import ProjectStatus, ReconstructionOptions
from .storage import (
    append_log,
    exports_dir,
    images_dir,
    load_metadata,
    nerfstudio_data_dir,
    outputs_dir,
    project_dir,
    save_metadata,
    set_status,
)


def _require_binary(binary: str) -> None:
    if shutil.which(binary) is None:
        raise RuntimeError(
            f"Missing executable '{binary}'. Install Nerfstudio/COLMAP tools "
            "or set the corresponding SUBTWIN_*_BIN environment variable."
        )


def _run(project_id: str, command: list[str], *, env: dict[str, str]) -> None:
    append_log(project_id, "")
    append_log(project_id, "$ " + " ".join(command))
    process = subprocess.Popen(
        command,
        cwd=project_dir(project_id),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        append_log(project_id, line)
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"Command failed with exit code {return_code}: {' '.join(command)}")


def _latest_config(search_dir: Path) -> Path:
    configs = sorted(search_dir.rglob("config.yml"), key=lambda path: path.stat().st_mtime)
    if not configs:
        raise RuntimeError(f"No Nerfstudio config.yml found under {search_dir}")
    return configs[-1]


def _latest_splat(search_dir: Path) -> Path:
    candidates = []
    for pattern in ("*.ply", "*.splat", "*.ksplat"):
        candidates.extend(search_dir.rglob(pattern))
    if not candidates:
        raise RuntimeError(f"No exported splat file found under {search_dir}")
    return sorted(candidates, key=lambda path: path.stat().st_mtime)[-1]


def _run_vggt_colmap(project_id: str, options: ReconstructionOptions) -> dict:
    if settings.vggt_repo is None:
        raise RuntimeError("Set SUBTWIN_VGGT_REPO to your local facebookresearch/vggt checkout.")
    demo_script = settings.vggt_repo / "demo_colmap.py"
    if not demo_script.exists():
        raise RuntimeError(f"VGGT demo_colmap.py not found: {demo_script}")

    env = os.environ.copy()
    if options.gpu_ids:
        env["CUDA_VISIBLE_DEVICES"] = options.gpu_ids

    cmd = [
        settings.python_bin,
        str(demo_script),
        f"--scene_dir={project_dir(project_id)}",
        f"--conf_thres_value={options.vggt_conf_thres_value}",
    ]
    if options.method == "vggt-colmap-ba":
        cmd.append("--use_ba")
    _run(project_id, cmd, env=env)

    sparse_dir = project_dir(project_id) / "sparse"
    points3d_path = sparse_dir / "points3D.bin"
    if not points3d_path.exists():
        sparse_candidates = sorted(project_dir(project_id).rglob("points3D.bin"))
        if not sparse_candidates:
            raise RuntimeError("VGGT finished but no points3D.bin was found.")
        points3d_path = sparse_candidates[-1]

    ply_path = exports_dir(project_id) / "point_cloud" / "points.ply"
    point_count = colmap_points_to_ply(points3d_path, ply_path)
    append_log(project_id, f"Exported point cloud: {ply_path} ({point_count} points)")
    return {
        "point_cloud_url": f"/data/projects/{project_id}/exports/point_cloud/{ply_path.name}",
        "point_cloud_filename": ply_path.name,
        "point_count": point_count,
        "colmap_sparse": str(points3d_path.parent),
        "reconstruction_mode": options.method,
    }


def _run_nerfstudio_splatfacto(project_id: str, options: ReconstructionOptions, meta_image_count: int) -> dict:
    _require_binary(settings.ns_process_data_bin)
    _require_binary(settings.ns_train_bin)
    _require_binary(settings.ns_export_bin)

    if meta_image_count < 3:
        raise RuntimeError("At least 3 images are required; 50+ is recommended.")

    env = os.environ.copy()
    if options.gpu_ids:
        env["CUDA_VISIBLE_DEVICES"] = options.gpu_ids

    ns_data = nerfstudio_data_dir(project_id)
    train_outputs = outputs_dir(project_id)
    export_path = exports_dir(project_id) / "splat"
    ns_data.mkdir(parents=True, exist_ok=True)
    train_outputs.mkdir(parents=True, exist_ok=True)
    export_path.mkdir(parents=True, exist_ok=True)

    process_cmd = [
        settings.ns_process_data_bin,
        "images",
        "--data",
        str(images_dir(project_id)),
        "--output-dir",
        str(ns_data),
        "--matching-method",
        options.matching_method,
    ]
    _run(project_id, process_cmd, env=env)

    train_cmd = [
        settings.ns_train_bin,
        options.method,
        "--data",
        str(ns_data),
        "--output-dir",
        str(train_outputs),
        "--max-num-iterations",
        str(options.max_num_iterations),
    ]
    if options.high_quality:
        append_log(
            project_id,
            "High-quality mode is currently represented by the iteration budget; "
            "method-specific tuning flags are intentionally left to Nerfstudio defaults.",
        )
    _run(project_id, train_cmd, env=env)

    config_path = _latest_config(train_outputs)
    export_cmd = [
        settings.ns_export_bin,
        "gaussian-splat",
        "--load-config",
        str(config_path),
        "--output-dir",
        str(export_path),
    ]
    _run(project_id, export_cmd, env=env)

    splat_path = _latest_splat(export_path)
    append_log(project_id, f"Exported splat: {splat_path}")
    return {
        "splat_url": f"/data/projects/{project_id}/exports/splat/{splat_path.name}",
        "splat_filename": splat_path.name,
        "nerfstudio_config": str(config_path),
        "reconstruction_mode": options.method,
    }


def run_reconstruction(project_id: str, options: ReconstructionOptions) -> None:
    meta = load_metadata(project_id)
    meta.options = options
    meta.status = ProjectStatus.running
    meta.error = None
    save_metadata(meta)

    try:
        if meta.image_count < 3:
            raise RuntimeError("At least 3 images are required; 50+ is recommended.")

        append_log(project_id, f"Project: {meta.name} ({project_id})")
        append_log(project_id, f"Images: {meta.image_count}")
        append_log(project_id, f"Method: {options.method}")
        if options.gpu_ids:
            append_log(project_id, f"CUDA_VISIBLE_DEVICES={options.gpu_ids}")

        if options.method in {"vggt-colmap", "vggt-colmap-ba"}:
            artifacts = _run_vggt_colmap(project_id, options)
        else:
            artifacts = _run_nerfstudio_splatfacto(project_id, options, meta.image_count)
        set_status(project_id, ProjectStatus.succeeded, artifacts=artifacts)
    except Exception as exc:
        append_log(project_id, f"ERROR: {exc}")
        set_status(project_id, ProjectStatus.failed, error=str(exc))
