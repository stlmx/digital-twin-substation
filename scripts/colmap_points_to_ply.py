#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.colmap import colmap_points_to_ply  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert COLMAP points3D.bin to browser-viewable PLY.")
    parser.add_argument("points3d_bin", type=Path)
    parser.add_argument("output_ply", type=Path)
    parser.add_argument("--max-points", type=int, default=2_000_000)
    args = parser.parse_args()

    count = colmap_points_to_ply(args.points3d_bin, args.output_ply, max_points=args.max_points)
    print(f"wrote {count} points to {args.output_ply}")


if __name__ == "__main__":
    main()
