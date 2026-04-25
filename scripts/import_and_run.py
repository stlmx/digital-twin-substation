#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.models import ProjectStatus, ReconstructionOptions  # noqa: E402
from app.pipeline import run_reconstruction  # noqa: E402
from app.storage import create_project, import_image_folder, load_metadata, save_metadata  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a reconstruction project from a local image folder and optionally run it."
    )
    parser.add_argument("folder", type=Path)
    parser.add_argument("--name", default="substation-scene")
    parser.add_argument("--mode", choices=["symlink", "copy"], default="symlink")
    parser.add_argument("--method", default="vggt-colmap")
    parser.add_argument("--iterations", type=int, default=30000)
    parser.add_argument("--gpu-ids", default=None)
    parser.add_argument("--matching-method", default="exhaustive")
    parser.add_argument("--no-run", action="store_true")
    args = parser.parse_args()

    metadata = create_project(args.name)
    count = import_image_folder(metadata.id, args.folder, mode=args.mode)
    if count < 3:
        raise SystemExit("At least 3 images are required.")

    options = ReconstructionOptions(
        method=args.method,
        max_num_iterations=args.iterations,
        gpu_ids=args.gpu_ids,
        matching_method=args.matching_method,
        high_quality=True,
    )
    metadata = load_metadata(metadata.id)
    metadata.options = options
    metadata.status = ProjectStatus.created if args.no_run else ProjectStatus.queued
    save_metadata(metadata)

    print(f"project_id: {metadata.id}")
    print(f"image_count: {count}")
    if args.no_run:
        return

    run_reconstruction(metadata.id, options)
    metadata = load_metadata(metadata.id)
    print(f"status: {metadata.status}")
    print(f"artifacts: {metadata.artifacts}")


if __name__ == "__main__":
    main()
