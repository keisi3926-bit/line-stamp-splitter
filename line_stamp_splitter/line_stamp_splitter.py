#!/usr/bin/env python3
"""LINE Creators Market static sticker image splitter and packer."""

from __future__ import annotations

import argparse
import math
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageChops


VALID_COUNTS = {8, 16, 24, 32, 40}
STICKER_MAX_SIZE = (370, 320)
MAIN_SIZE = (240, 240)
TAB_SIZE = (96, 74)
MAX_FILE_BYTES = 1024 * 1024
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class ProcessOptions:
    padding: int = 12
    remove_white_bg: bool = False
    white_threshold: int = 245


@dataclass
class Report:
    infos: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI生成スタンプ画像をLINE Creators Market向けPNG/ZIPへ整形します。"
    )
    parser.add_argument("input", help="入力画像、または画像フォルダ")
    parser.add_argument("--rows", type=int, help="グリッド画像の行数")
    parser.add_argument("--cols", type=int, help="グリッド画像の列数")
    parser.add_argument("--count", type=int, required=True, help="スタンプ数: 8/16/24/32/40")
    parser.add_argument("--output", default="output_line_stickers", help="出力フォルダ")
    parser.add_argument("--padding", type=int, default=12, help="トリミング後に追加する透明余白px")
    parser.add_argument("--remove-white-bg", action="store_true", help="白背景に近い領域を透明化")
    parser.add_argument("--white-threshold", type=int, default=245, help="白背景判定しきい値 0-255")
    parser.add_argument("--main-index", type=int, default=1, help="main.png生成元のスタンプ番号")
    parser.add_argument("--tab-index", type=int, default=1, help="tab.png生成元のスタンプ番号")
    parser.add_argument("--zip", action="store_true", help="line_stickers.zipを作成")
    parser.add_argument("--overwrite", action="store_true", help="出力フォルダ内の既存PNG/ZIP/reportを上書き")
    return parser.parse_args(argv)


def validate_cli_args(args: argparse.Namespace) -> None:
    if args.count not in VALID_COUNTS:
        raise ValueError("--count は 8 / 16 / 24 / 32 / 40 のいずれかを指定してください。")
    if args.padding < 0:
        raise ValueError("--padding は0以上を指定してください。")
    if not 0 <= args.white_threshold <= 255:
        raise ValueError("--white-threshold は0から255の範囲で指定してください。")
    if not 1 <= args.main_index <= args.count:
        raise ValueError("--main-index は1からcountの範囲で指定してください。")
    if not 1 <= args.tab_index <= args.count:
        raise ValueError("--tab-index は1からcountの範囲で指定してください。")
    has_grid_option = args.rows is not None or args.cols is not None
    if has_grid_option and (not args.rows or not args.cols):
        raise ValueError("グリッド入力では --rows と --cols の両方を指定してください。")
    if args.rows is not None and args.cols is not None:
        if args.rows <= 0 or args.cols <= 0:
            raise ValueError("--rows / --cols は1以上を指定してください。")
        if args.rows * args.cols < args.count:
            raise ValueError("--rows × --cols が --count より少ないため切り出せません。")


def load_images(input_path: Path, count: int, rows: int | None = None, cols: int | None = None) -> list[Image.Image]:
    if input_path.is_dir():
        files = sorted(
            p for p in input_path.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        if len(files) < count:
            raise ValueError(f"入力フォルダ内の対応画像が不足しています: {len(files)}枚 / 必要{count}枚")
        return [Image.open(path).convert("RGBA") for path in files[:count]]

    if not input_path.is_file():
        raise FileNotFoundError(f"入力が見つかりません: {input_path}")

    image = Image.open(input_path).convert("RGBA")
    if rows and cols:
        return split_grid_image(image, rows, cols, count)
    return [image]


def split_grid_image(image: Image.Image, rows: int, cols: int, count: int) -> list[Image.Image]:
    cell_w = image.width / cols
    cell_h = image.height / rows
    cells: list[Image.Image] = []
    for index in range(count):
        row = index // cols
        col = index % cols
        box = (
            int(round(col * cell_w)),
            int(round(row * cell_h)),
            int(round((col + 1) * cell_w)),
            int(round((row + 1) * cell_h)),
        )
        cells.append(image.crop(box))
    return cells


def remove_white_background(image: Image.Image, threshold: int = 245) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a and r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def trim_transparent_or_white_margin(
    image: Image.Image,
    white_threshold: int = 245,
    treat_white_as_empty: bool = False,
) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_bbox = alpha.getbbox()

    if not treat_white_as_empty:
        bbox = alpha_bbox
    else:
        pixels = rgba.load()
        min_x, min_y = rgba.width, rgba.height
        max_x, max_y = -1, -1
        for y in range(rgba.height):
            for x in range(rgba.width):
                r, g, b, a = pixels[x, y]
                visible = a > 0 and not (r >= white_threshold and g >= white_threshold and b >= white_threshold)
                if visible:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        bbox = None if max_x < 0 else (min_x, min_y, max_x + 1, max_y + 1)

    if bbox is None:
        return Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    return rgba.crop(bbox)


def add_padding(image: Image.Image, padding: int) -> Image.Image:
    width = max(2, image.width + padding * 2)
    height = max(2, image.height + padding * 2)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(image.convert("RGBA"), (padding, padding))
    return canvas


def even_dimension(value: int) -> int:
    return max(2, value if value % 2 == 0 else value + 1)


def fit_to_line_sticker_size(image: Image.Image, max_size: tuple[int, int] = STICKER_MAX_SIZE) -> Image.Image:
    rgba = image.convert("RGBA")
    scale = min(max_size[0] / rgba.width, max_size[1] / rgba.height, 1.0)
    new_w = even_dimension(max(2, int(math.floor(rgba.width * scale))))
    new_h = even_dimension(max(2, int(math.floor(rgba.height * scale))))
    if (new_w, new_h) != rgba.size:
        rgba = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return rgba


def process_sticker(image: Image.Image, options: ProcessOptions) -> Image.Image:
    rgba = image.convert("RGBA")
    if options.remove_white_bg:
        rgba = remove_white_background(rgba, options.white_threshold)
    trimmed = trim_transparent_or_white_margin(
        rgba,
        white_threshold=options.white_threshold,
        treat_white_as_empty=options.remove_white_bg,
    )
    padded = add_padding(trimmed, options.padding)
    return fit_to_line_sticker_size(padded)


def create_exact_canvas_image(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    trimmed = trim_transparent_or_white_margin(source, treat_white_as_empty=False)
    scale = min(size[0] / trimmed.width, size[1] / trimmed.height, 1.0)
    new_w = max(1, int(math.floor(trimmed.width * scale)))
    new_h = max(1, int(math.floor(trimmed.height * scale)))
    resized = trimmed.resize((new_w, new_h), Image.Resampling.LANCZOS) if trimmed.size != (new_w, new_h) else trimmed
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(resized.convert("RGBA"), ((size[0] - new_w) // 2, (size[1] - new_h) // 2))
    return canvas


def create_main_image(source: Image.Image) -> Image.Image:
    return create_exact_canvas_image(source, MAIN_SIZE)


def create_tab_image(source: Image.Image) -> Image.Image:
    return create_exact_canvas_image(source, TAB_SIZE)


def save_png_under_limit(image: Image.Image, path: Path, report: Report) -> None:
    image.save(path, "PNG", optimize=True, compress_level=9, dpi=(72, 72))
    if path.stat().st_size <= MAX_FILE_BYTES:
        return

    current = image
    for shrink in (0.95, 0.9, 0.85, 0.8, 0.7):
        new_size = (even_dimension(int(current.width * shrink)), even_dimension(int(current.height * shrink)))
        if new_size[0] < 2 or new_size[1] < 2:
            break
        current = image.resize(new_size, Image.Resampling.LANCZOS)
        current.save(path, "PNG", optimize=True, compress_level=9, dpi=(72, 72))
        if path.stat().st_size <= MAX_FILE_BYTES:
            report.warning(f"{path.name}: 1MB以下にするため {new_size[0]}x{new_size[1]} に縮小しました。")
            return
    report.warning(f"{path.name}: 1MBを超えています ({path.stat().st_size} bytes)。")


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        existing = [p.name for p in output_dir.iterdir() if p.suffix.lower() in {".png", ".zip", ".txt"}]
        if existing:
            raise FileExistsError(
                f"出力フォルダに既存ファイルがあります: {output_dir}。上書きする場合は --overwrite を付けてください。"
            )
    for path in output_dir.iterdir():
        if path.is_file() and path.suffix.lower() in {".png", ".zip", ".txt"}:
            path.unlink()


def has_transparency(image: Image.Image) -> bool:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    return alpha.getextrema()[0] < 255


def validate_outputs(output_dir: Path, count: int, report: Report) -> None:
    if count not in VALID_COUNTS:
        report.error(f"スタンプ数が不正です: {count}")
    else:
        report.info(f"スタンプ数OK: {count}")

    expected = [output_dir / f"{i:02d}.png" for i in range(1, count + 1)]
    expected += [output_dir / "main.png", output_dir / "tab.png"]

    for path in expected:
        if not path.exists():
            report.error(f"{path.name}: ファイルがありません。")
            continue
        if path.suffix.lower() != ".png":
            report.error(f"{path.name}: PNG形式ではありません。")
        if path.stat().st_size > MAX_FILE_BYTES:
            report.warning(f"{path.name}: 1MBを超えています ({path.stat().st_size} bytes)。")

        with Image.open(path) as image:
            width, height = image.size
            if image.format != "PNG":
                report.error(f"{path.name}: PNG形式ではありません。")
            if path.name == "main.png":
                if image.size != MAIN_SIZE:
                    report.error(f"main.png: サイズが240x240ではありません ({width}x{height})。")
            elif path.name == "tab.png":
                if image.size != TAB_SIZE:
                    report.error(f"tab.png: サイズが96x74ではありません ({width}x{height})。")
            else:
                if width > STICKER_MAX_SIZE[0] or height > STICKER_MAX_SIZE[1]:
                    report.error(f"{path.name}: 370x320を超えています ({width}x{height})。")
            if width % 2 or height % 2:
                report.error(f"{path.name}: 縦横のいずれかが奇数pxです ({width}x{height})。")
            if image.mode not in {"RGB", "RGBA", "P", "LA"}:
                report.warning(f"{path.name}: 画像モードが想定外です ({image.mode})。")
            dpi = image.info.get("dpi")
            if dpi:
                x_dpi, y_dpi = dpi
                if x_dpi < 72 or y_dpi < 72:
                    report.warning(f"{path.name}: DPIが72未満です ({x_dpi:.1f}, {y_dpi:.1f})。")
            else:
                report.warning(f"{path.name}: DPI情報がありません。")
            if not has_transparency(image):
                report.warning(f"{path.name}: 透過ピクセルが検出できません。")


def create_zip(output_dir: Path, count: int) -> Path:
    zip_path = output_dir / "line_stickers.zip"
    names = ["main.png", "tab.png"] + [f"{i:02d}.png" for i in range(1, count + 1)]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            zf.write(output_dir / name, arcname=name)
    return zip_path


def write_report(output_dir: Path, report: Report, count: int, zipped: bool) -> Path:
    path = output_dir / "report.txt"
    lines = [
        "LINE Creators Market スタンプ画像処理レポート",
        "",
        f"スタンプ数: {count}",
        f"ZIP作成: {'あり' if zipped else 'なし'}",
        "",
        "[INFO]",
        *(report.infos or ["なし"]),
        "",
        "[WARNINGS]",
        *(report.warnings or ["なし"]),
        "",
        "[ERRORS]",
        *(report.errors or ["なし"]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8-sig")
    return path


def run(args: argparse.Namespace) -> int:
    validate_cli_args(args)
    input_path = Path(args.input)
    output_dir = Path(args.output)
    report = Report()

    prepare_output_dir(output_dir, args.overwrite)
    images = load_images(input_path, args.count, args.rows, args.cols)
    if len(images) < args.count:
        raise ValueError(f"処理対象画像が不足しています: {len(images)}枚 / 必要{args.count}枚")

    options = ProcessOptions(
        padding=args.padding,
        remove_white_bg=args.remove_white_bg,
        white_threshold=args.white_threshold,
    )
    processed = [process_sticker(image, options) for image in images[: args.count]]

    for index, image in enumerate(processed, start=1):
        save_png_under_limit(image, output_dir / f"{index:02d}.png", report)

    save_png_under_limit(create_main_image(processed[args.main_index - 1]), output_dir / "main.png", report)
    save_png_under_limit(create_tab_image(processed[args.tab_index - 1]), output_dir / "tab.png", report)

    zip_path = None
    if args.zip:
        zip_path = create_zip(output_dir, args.count)
        report.info(f"ZIP作成: {zip_path.name}")

    validate_outputs(output_dir, args.count, report)
    report_path = write_report(output_dir, report, args.count, zipped=bool(zip_path))

    print(f"完了: {output_dir}")
    print(f"レポート: {report_path}")
    if report.errors:
        print("エラーがあります。report.txtを確認してください。", file=sys.stderr)
        return 2
    if report.warnings:
        print("警告があります。report.txtを確認してください。")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except Exception as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
