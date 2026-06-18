#!/usr/bin/env python3
"""Create simple dummy images for line_stamp_splitter manual testing."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


COLORS = [
    (232, 82, 77, 255),
    (57, 146, 204, 255),
    (75, 168, 91, 255),
    (244, 180, 64, 255),
    (154, 93, 190, 255),
    (30, 160, 150, 255),
    (230, 112, 172, 255),
    (100, 110, 125, 255),
]


def make_sticker(index: int, size: tuple[int, int] = (512, 512), white_bg: bool = True) -> Image.Image:
    bg = (255, 255, 255, 255) if white_bg else (0, 0, 0, 0)
    image = Image.new("RGBA", size, bg)
    draw = ImageDraw.Draw(image)
    color = COLORS[index % len(COLORS)]
    margin = 80 + (index % 4) * 8
    draw.rounded_rectangle(
        (margin, margin + 20, size[0] - margin, size[1] - margin - 20),
        radius=48,
        fill=color,
        outline=(40, 40, 40, 255),
        width=8,
    )
    draw.text((size[0] // 2 - 20, size[1] // 2 - 18), f"{index + 1}", fill=(255, 255, 255, 255))
    return image


def create_folder(output: Path, count: int, white_bg: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        make_sticker(i, white_bg=white_bg).save(output / f"dummy_{i + 1:02d}.png")


def create_grid(output: Path, rows: int, cols: int, count: int, white_bg: bool) -> None:
    cell = (512, 512)
    grid = Image.new("RGBA", (cols * cell[0], rows * cell[1]), (255, 255, 255, 255))
    for i in range(count):
        sticker = make_sticker(i, cell, white_bg=white_bg)
        grid.alpha_composite(sticker, ((i % cols) * cell[0], (i // cols) * cell[1]))
    output.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="テスト用ダミー画像を生成します。")
    parser.add_argument("--output", default="dummy_input", help="出力先フォルダまたはPNGパス")
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument("--grid", action="store_true", help="1枚のグリッド画像として生成")
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--transparent", action="store_true", help="透明背景で生成")
    args = parser.parse_args()

    output = Path(args.output)
    if args.grid:
        create_grid(output, args.rows, args.cols, args.count, white_bg=not args.transparent)
    else:
        create_folder(output, args.count, white_bg=not args.transparent)
    print(f"作成しました: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
