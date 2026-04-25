from __future__ import annotations

import struct
from pathlib import Path


def read_points3d_binary(path: Path) -> list[tuple[float, float, float, int, int, int]]:
    points: list[tuple[float, float, float, int, int, int]] = []
    with path.open("rb") as handle:
        num_points = struct.unpack("<Q", handle.read(8))[0]
        for _ in range(num_points):
            _point_id = struct.unpack("<Q", handle.read(8))[0]
            x, y, z = struct.unpack("<ddd", handle.read(24))
            r, g, b = struct.unpack("<BBB", handle.read(3))
            _error = struct.unpack("<d", handle.read(8))[0]
            track_length = struct.unpack("<Q", handle.read(8))[0]
            handle.seek(track_length * 8, 1)
            points.append((x, y, z, r, g, b))
    return points


def write_ascii_ply(
    points: list[tuple[float, float, float, int, int, int]],
    path: Path,
    *,
    max_points: int | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if max_points and len(points) > max_points:
        stride = max(1, len(points) // max_points)
        points = points[::stride][:max_points]

    with path.open("w", encoding="utf-8") as handle:
        handle.write("ply\n")
        handle.write("format ascii 1.0\n")
        handle.write(f"element vertex {len(points)}\n")
        handle.write("property float x\n")
        handle.write("property float y\n")
        handle.write("property float z\n")
        handle.write("property uchar red\n")
        handle.write("property uchar green\n")
        handle.write("property uchar blue\n")
        handle.write("end_header\n")
        for x, y, z, r, g, b in points:
            handle.write(f"{x:.7f} {y:.7f} {z:.7f} {r} {g} {b}\n")


def colmap_points_to_ply(points3d_path: Path, ply_path: Path, *, max_points: int = 2_000_000) -> int:
    points = read_points3d_binary(points3d_path)
    write_ascii_ply(points, ply_path, max_points=max_points)
    return min(len(points), max_points)
