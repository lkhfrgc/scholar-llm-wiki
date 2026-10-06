#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把官方 LibreOffice Kit 渲染出的页图，按公式块 bbox 裁成小图。

为什么这样做：LibreOffice Kit 支持 PDF → PNG（pdfium），但不支持区域裁剪；
而公式只占页面很小一块（实测 ~5% 面积），整页喂给模型要浪费几十倍 token。
这里用 bbox 把公式单独裁出来，只把小图交给模型核对。

坐标约定：extract_pdf.py --equations-json 给出的 bbox 是 **PDF 点坐标（原点左上）**，
渲染图像素 = 点 × (dpi / 72)。本脚本优先用 manifest 里的实际宽高反推比例，
避免四舍五入误差。

依赖：只需要 Pillow —— harness 自带 Python 通常已内置，用 `python` 即可运行，
**不需要项目 venv**（项目 venv 只用来装 PyMuPDF）。缺 Pillow 时按提示补装：
    Windows      `.dsh\\venv\\Scripts\\python.exe -m pip install -r .dsh/requirements.txt`
    macOS/Linux  `.dsh/venv/bin/python       -m pip install -r .dsh/requirements.txt`

用法：
    python .dsh/scripts/crop_equations.py \\
        --manifest <tmp>/render/manifest.json \\
        --equations <tmp>/paper.equations.json \\
        --out-dir <tmp>/eqcrops --pages 3

选项：
    --manifest    LibreOffice Kit `render` 产出的 manifest.json（Kit 路径由 office 相关技能提供）
    --equations   extract_pdf.py --equations-json 产出的 sidecar
    --out-dir     裁剪结果目录（不存在会新建）
    --pages       可选，只裁这些页（如 3,5 或 3-7）
    --pad         可选，四周留白像素（默认 6）
    --json-out    可选，索引 JSON 路径（默认 <out-dir>/equations_index.json）

中间产物目录由 `.dsh/wiki.config.json` 的 `dirs.tmp` 决定（默认 `.dsh/tmp`，
即 `wiki_env.tmp_dir()`），不要在命令或脚本里写死。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

# ── 路径与编码：全仓唯一来源是 wiki_env ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, ensure_utf8_stdio, tmp_dir  # noqa: E402

PILLOW_HINT = (
    "错误：未安装 Pillow —— 本脚本需要它来裁剪图像。\n"
    "安装：\n"
    "  python -m venv .dsh/venv\n"
    "  # Windows:     .dsh\\venv\\Scripts\\python.exe -m pip install -r .dsh/requirements.txt\n"
    "  # macOS/Linux: .dsh/venv/bin/python -m pip install -r .dsh/requirements.txt"
)


def _load_image_class():
    """延迟导入 Pillow；缺失时打印安装指引并以退出码 1 结束。"""
    try:
        from PIL import Image  # type: ignore
        return Image
    except ImportError:
        print(PILLOW_HINT, file=sys.stderr)
        raise SystemExit(1)


def _rel(path: Path) -> str:
    """把工作区内路径显示成相对形式，避免帮助文本里出现机器专属的绝对路径。"""
    try:
        return path.relative_to(WS).as_posix()
    except ValueError:
        return path.as_posix()


def parse_pages(arg: str | None) -> set | None:
    if not arg:
        return None
    out: set = set()
    for part in arg.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="按公式块 bbox 裁剪 Kit 渲染页图",
        epilog=f"中间产物目录（来自配置）：{_rel(tmp_dir())}",
    )
    ap.add_argument("--manifest", required=True, help="Kit render 产出的 manifest.json")
    ap.add_argument("--equations", required=True, help="extract_pdf.py --equations-json 的 sidecar")
    ap.add_argument("--out-dir", required=True, help="裁剪结果目录（不存在会新建）")
    ap.add_argument("--pages", default=None, help="只裁这些页，如 3,5 或 3-7")
    ap.add_argument("--pad", type=int, default=6, help="四周留白像素（默认 6）")
    ap.add_argument("--json-out", default=None, help="索引 JSON 路径（默认 <out-dir>/equations_index.json）")
    args = ap.parse_args(argv)

    Image = _load_image_class()

    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)
    with open(args.equations, encoding="utf-8") as fh:
        equations = json.load(fh)

    only_pages = parse_pages(args.pages)
    eq_by_page = {int(p["page"]): p for p in equations.get("pages", [])}
    dpi = float(manifest.get("dpi") or 144.0)

    os.makedirs(args.out_dir, exist_ok=True)
    index: List[dict] = []
    total_bytes = 0
    missing: List[str] = []

    for image in manifest.get("images", []):
        page_no = int(image.get("page") or 0)
        if only_pages and page_no not in only_pages:
            continue
        entry = eq_by_page.get(page_no)
        if not entry or not entry.get("equations"):
            missing.append(f"第 {page_no} 页：sidecar 中没有公式块")
            continue

        path = image.get("path")
        if not path or not os.path.exists(path):
            missing.append(f"第 {page_no} 页：manifest 指向的图像不存在（{path}）")
            continue

        rect = image.get("rectangle") or {}
        img = Image.open(path)

        # 坐标换算（踩过的坑）：sidecar 的 bbox 是 PDF 点，而 manifest.rectangle
        # 是 96 dpi 的 CSS 像素（实测 letter 页 w=816 = 612pt × 4/3，而渲染图宽
        # 1700 = 612pt × 200/72）。这里按实际图像宽高反推「每点像素数」，
        # 并做一致性检查，避免 Kit 因 maxPixels 限制而悄悄降采样时算错。
        rect_w = float(rect.get("width") or 0.0)
        unit_to_point = 72.0 / 96.0
        if rect_w > 0 and abs(img.width - rect_w * dpi / 96.0) <= 2:
            scale = img.width / (rect_w * unit_to_point)      # rectangle 为 96dpi 单位
        elif rect_w > 0 and abs(img.width - rect_w * dpi / 72.0) <= 2:
            unit_to_point = 1.0
            scale = img.width / rect_w                        # rectangle 为 PDF 点
        else:
            scale = (img.width / rect_w) if rect_w > 0 else (dpi / 72.0)
            print(
                f"[警告] 第 {page_no} 页：渲染尺寸与 manifest 不符"
                f"（图宽 {img.width}px, rectangle 宽 {rect_w}），已按 96dpi 单位换算 scale={scale:.4f}",
                file=sys.stderr,
            )
        off_x = float(rect.get("x") or 0.0) * unit_to_point
        off_y = float(rect.get("y") or 0.0) * unit_to_point

        for i, eq in enumerate(entry["equations"], 1):
            x0, y0, x1, y1 = eq["bbox"]
            box = (
                max(0, int((x0 - off_x) * scale) - args.pad),
                max(0, int((y0 - off_y) * scale) - args.pad),
                min(img.width, int((x1 - off_x) * scale) + args.pad),
                min(img.height, int((y1 - off_y) * scale) + args.pad),
            )
            if box[2] <= box[0] or box[3] <= box[1]:
                missing.append(f"第 {page_no} 页公式块 {i}：bbox 越界，已跳过")
                continue
            crop = img.crop(box)
            out_path = os.path.join(args.out_dir, f"eq_p{page_no}_{i}.png")
            crop.save(out_path)
            size = os.path.getsize(out_path)
            total_bytes += size
            index.append({
                "page": page_no,
                "index": i,
                "path": out_path,
                "bbox": eq["bbox"],
                "pixels": [crop.width, crop.height],
                "bytes": size,
                "text": eq.get("text", ""),
            })

    json_out = args.json_out or os.path.join(args.out_dir, "equations_index.json")
    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump({
            "source_pdf": equations.get("file"),
            "source_sha256": equations.get("source_sha256"),
            "dpi": dpi,
            "crops": index,
        }, fh, ensure_ascii=False, indent=2)

    print(f"[完成] 裁出 {len(index)} 张公式图，合计 {total_bytes / 1024:.1f} KB → {os.path.abspath(args.out_dir)}")
    for item in index:
        snippet = item["text"][:64].replace("\n", " ")
        print(f"  p{item['page']}#{item['index']}  {item['pixels'][0]}×{item['pixels'][1]}px  "
              f"{item['bytes'] / 1024:.1f} KB  {item['path']}  | {snippet}")
    print(f"[索引] {os.path.abspath(json_out)}")
    for note in missing:
        print(f"[提示] {note}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
