#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a reconstruction image set.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--thumb-width", type=int, default=220)
    parser.add_argument("--thumb-height", type=int, default=160)
    args = parser.parse_args()

    image_paths = [
        path
        for path in sorted(args.folder.iterdir())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    if not image_paths:
        raise SystemExit(f"No images found in {args.folder}")

    dimensions: Counter[tuple[int, int]] = Counter()
    thumbnails: list[Image.Image] = []
    total_pixels = 0

    for path in image_paths:
        with Image.open(path) as image:
            dimensions[image.size] += 1
            total_pixels += image.size[0] * image.size[1]
            if args.contact_sheet:
                thumbnail = ImageOps.exif_transpose(image.copy())
                thumbnail.thumbnail((args.thumb_width, args.thumb_height))
                canvas = Image.new(
                    "RGB",
                    (args.thumb_width, args.thumb_height + 25),
                    (245, 247, 245),
                )
                canvas.paste(thumbnail, ((args.thumb_width - thumbnail.width) // 2, 0))
                thumbnails.append(canvas)

    print(f"folder: {args.folder}")
    print(f"images: {len(image_paths)}")
    print(f"avg_megapixels: {total_pixels / len(image_paths) / 1_000_000:.2f}")
    print("dimensions:")
    for (width, height), count in dimensions.most_common():
        print(f"  {width}x{height}: {count}")

    videos = sorted(path for path in args.folder.iterdir() if path.suffix.lower() in {".mp4", ".mov", ".m4v"})
    if videos:
        print("videos:")
        for video in videos:
            print(f"  {video.name}")

    if args.contact_sheet:
        columns = 7
        rows = (len(thumbnails) + columns - 1) // columns
        sheet = Image.new(
            "RGB",
            (columns * args.thumb_width, rows * (args.thumb_height + 25)),
            (238, 242, 239),
        )
        for index, thumbnail in enumerate(thumbnails):
            sheet.paste(
                thumbnail,
                (
                    (index % columns) * args.thumb_width,
                    (index // columns) * (args.thumb_height + 25),
                ),
            )
        args.contact_sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.contact_sheet, quality=90)
        print(f"contact_sheet: {args.contact_sheet}")


if __name__ == "__main__":
    main()
