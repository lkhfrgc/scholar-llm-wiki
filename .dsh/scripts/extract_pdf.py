#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可复用 PDF 全文提取脚本（PyMuPDF）。
使用 PyMuPDF 提取 PDF 的全部文本内容，自动处理多栏排版。

依赖：需要能 `import pymupdf`（PyMuPDF >= 1.24）的解释器。解释器写法对照：
    harness 自带 Python   直接写 `python`（前提是该解释器已装 PyMuPDF）
    项目 venv             Windows      `.dsh\\venv\\Scripts\\python.exe`
                          macOS/Linux  `.dsh/venv/bin/python`
    <venv-python> .dsh/scripts/extract_pdf.py "<pdf_path>" -o output.txt

    # 建隔离环境并安装依赖（不要往系统 Python 装包）
    python -m venv .dsh/venv
    # Windows:     .dsh\\venv\\Scripts\\python.exe -m pip install -r .dsh/requirements.txt
    # macOS/Linux: .dsh/venv/bin/python -m pip install -r .dsh/requirements.txt

用法：
    python extract_pdf.py <pdf_path> -o output.txt   # 写入文件（推荐，避免编码问题）
    python extract_pdf.py <pdf_path>                  # 输出纯文本全文到 stdout
    python extract_pdf.py <pdf_path> --json           # 输出 JSON（含 metadata + 全文）
    python extract_pdf.py <pdf_path> --pages 1-5      # 只提取指定页码范围
    python extract_pdf.py <pdf_path> --math           # 公式感知：重建上下标（_{}/^{}）+ 字体可靠性诊断
    python extract_pdf.py <pdf_path> --equations-json <tmp>/paper.equations.json   # 附写公式块 bbox（隐含 --math）

中间产物目录由 `.dsh/wiki.config.json` 的 `dirs.tmp` 决定（默认 `.dsh/tmp`，
即 `wiki_env.tmp_dir()`）；具体路径用 `python .dsh/scripts/wiki_env.py --paths` 查看，
不要在命令或脚本里写死。

公式处理三件套：
    ① 有 arXiv/DOI 源 → 先跑 fetch_source.py 取 LaTeX 真值（零损失，仅需标准库）
    ② 无源 → 本脚本 --math 抽正文并定位公式块（bbox 供裁剪；字体无 ToUnicode 的页会被标记）
    ③ 需要精确核对 → 官方 LibreOffice Kit 渲染页图 + crop_equations.py 按 bbox 裁剪
       （Kit 路径由 office 相关技能提供，本脚本不猜）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

# ── 路径与编码：全仓唯一来源是 wiki_env ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, ensure_utf8_stdio, tmp_dir  # noqa: E402

PYMUPDF_HINT = (
    "错误：未安装 PyMuPDF —— PDF 正文抽取需要它。\n"
    "安装：\n"
    "  python -m venv .dsh/venv\n"
    "  # Windows:     .dsh\\venv\\Scripts\\python.exe -m pip install -r .dsh/requirements.txt\n"
    "  # macOS/Linux: .dsh/venv/bin/python -m pip install -r .dsh/requirements.txt"
)

fitz = None  # 由 _load_fitz() 在 main() 里填充；模块导入时不做任何重活


def _load_fitz():
    """延迟导入 PyMuPDF；缺失时打印安装指引并以退出码 1 结束。

    延迟到调用点是为了让 `--help` 在没有 PyMuPDF 的解释器上也能正常工作。
    """
    global fitz
    if fitz is not None:
        return fitz
    try:
        # PyMuPDF >= 1.24 renamed the import to `pymupdf`; the legacy `fitz` alias
        # still works but prints a deprecation banner on import. Prefer the new name.
        import pymupdf as _fitz  # type: ignore
    except ImportError:
        try:
            import fitz as _fitz  # type: ignore # PyMuPDF (legacy alias)
        except ImportError:
            print(PYMUPDF_HINT, file=sys.stderr)
            raise SystemExit(1)
    fitz = _fitz
    return fitz


def _rel(path: Path) -> str:
    """把工作区内路径显示成相对形式，避免帮助文本里出现机器专属的绝对路径。"""
    try:
        return path.relative_to(WS).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# 文本清洗
# ---------------------------------------------------------------------------

def _sanitize_text(text: str) -> str:
    """清洗 PDF 提取文本中的常见噪声。"""
    # 替换 Unicode 替换字符（表示无法解码的字形）
    text = text.replace("\ufffd", "")
    # 替换零宽字符
    for zw in ["\u200b", "\u200c", "\u200d", "\ufeff"]:
        text = text.replace(zw, "")
    # 规范化换行：保留段落结构
    return text


# ---------------------------------------------------------------------------
# 公式感知：上下标重建 / 公式块定位 / 字体可靠性诊断
# ---------------------------------------------------------------------------
#
# 为什么需要这一层：PDF 里的公式是二维排版，直接 join 文本会把上下标拉平
# （P_s → Ps、x^2 → x2），把分式拆成两行，把大运算符的上下限抛到别处；
# 更糟的是部分 LaTeX 数学子集字体（CMEX/CMMI/CMSY…）没有 ToUnicode 表，
# 字形码会被当成 ASCII 解出来——行间 Σ 会变成 "P"/"X"。后者文本路径无法修复，
# 只能靠下面的诊断标记出来，交给视觉路径或源头（arXiv LaTeX）解决。

MATH_FONT_HINTS = (
    "CMMI", "CMSY", "CMEX", "MSAM", "MSBM",
    "Math", "Symbol", "MTMI", "MTSY", "STIX", "XITS",
)
# 数学字体缺 ToUnicode 时最常被错解成的 ASCII
SUSPECT_ASCII = set("PXQYZ[]{}|~^_`'\"\\/")


def _is_math_font(name: str) -> bool:
    low = (name or "").lower()
    return any(h.lower() in low for h in MATH_FONT_HINTS)


def _line_body_size(line: dict) -> float:
    """该行的主字号（按字符数加权）。"""
    sizes: dict = {}
    for s in line.get("spans", []):
        key = round(s["size"], 1)
        sizes[key] = sizes.get(key, 0) + len(s.get("text", ""))
    return max(sizes.items(), key=lambda kv: kv[1])[0] if sizes else 10.0


def _line_baseline(line: dict) -> Tuple[float, float]:
    """该行的基线 y 与主字号（取最大字号 span 为准）。"""
    spans = line.get("spans", [])
    if not spans:
        return 0.0, 10.0
    best = max(spans, key=lambda s: (round(s["size"], 1), len(s.get("text", ""))))
    return best["origin"][1], round(best["size"], 1)


def _classify_span(span: dict, base_y: float, base_size: float) -> str | None:
    """按字号 + 基线偏移判定 span 是上标、下标还是正文。"""
    size = span["size"]
    y = span["origin"][1]
    if size <= base_size * 0.85:
        if y < base_y - 0.12 * base_size:
            return "sup"
        if y > base_y + 0.12 * base_size:
            return "sub"
    return None


def _wrap_math(text: str, kind: str | None) -> str:
    if kind == "sup":
        return "^{" + text + "}"
    if kind == "sub":
        return "_{" + text + "}"
    return text


def _render_line_math(line: dict) -> str:
    """把一行还原成带 _{}/^{} 标记的文本。"""
    base_y, base_size = _line_baseline(line)
    parts: List[str] = []
    pending: List[str] = []
    pending_kind: str | None = None

    def flush() -> None:
        nonlocal pending, pending_kind
        if pending:
            parts.append(_wrap_math("".join(pending), pending_kind))
            pending = []
            pending_kind = None

    for s in line.get("spans", []):
        kind = _classify_span(s, base_y, base_size)
        for ch in s.get("text", ""):
            if kind is None:
                flush()
                parts.append(ch)
            else:
                if pending_kind is not None and kind != pending_kind:
                    flush()
                pending_kind = kind
                pending.append(ch)
    flush()
    return "".join(parts)


def _page_equations(page) -> Tuple[List[dict], List[dict]]:
    """定位疑似公式块（行级判定 + 纵向合并），并诊断数学字体的异常映射。

    返回 (公式块列表, 可疑字体样本)。bbox 为 PDF 点坐标、原点在左上角；
    crop_equations.py 按 dpi/72 缩放到渲染图像素。
    """
    d = page.get_text("dict")
    body = 10.0
    sizes: dict = {}
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                key = round(s["size"], 1)
                sizes[key] = sizes.get(key, 0) + len(s.get("text", ""))
    if sizes:
        body = max(sizes.items(), key=lambda kv: kv[1])[0]

    marked: List[Tuple[object, str]] = []
    suspects: List[dict] = []

    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(s.get("text", "") for s in spans)
            if not text.strip():
                continue

            for s in spans:
                if _is_math_font(s.get("font", "")):
                    bad = "".join(sorted({ch for ch in s.get("text", "") if ch in SUSPECT_ASCII}))
                    if bad:
                        suspects.append({
                            "font": s.get("font", ""),
                            "chars": bad,
                            "sample": s.get("text", "")[:40],
                        })

            math_chars = sum(len(s.get("text", "")) for s in spans if _is_math_font(s.get("font", "")))
            small = sum(len(s.get("text", "")) for s in spans if s["size"] < body * 0.85)
            ratio = math_chars / max(1, len(text))
            x0, _, x1, _ = line["bbox"]
            width = x1 - x0
            centered = abs((x0 + x1) / 2 - page.rect.width / 2) < page.rect.width * 0.10

            if ratio >= 0.40 or (
                ratio >= 0.18 and small >= 2 and centered and width < page.rect.width * 0.72
            ):
                marked.append((fitz.Rect(line["bbox"]), _render_line_math(line)))

    # 先在同一行带内横向合并（碎片间隙小 → 属于同一个公式），再纵向合并相邻行
    items = sorted(marked, key=lambda item: (round(item[0].y0, 1), item[0].x0))
    bands: List[dict] = []
    for rect, text in items:
        for band in bands:
            br = band["_rect"]
            v_overlap = min(rect.y1, br.y1) - max(rect.y0, br.y0)
            min_h = min(rect.height, br.height)
            h_gap = max(rect.x0 - br.x1, br.x0 - rect.x1)
            if min_h > 0 and v_overlap / min_h > 0.5 and h_gap < 30:
                band["_rect"] |= rect
                band["_texts"].append((round(rect.y0, 1), rect.x0, text))
                break
        else:
            bands.append({
                "_rect": fitz.Rect(rect),
                "_texts": [(round(rect.y0, 1), rect.x0, text)],
            })

    bands.sort(key=lambda band: band["_rect"].y0)
    blocks: List[dict] = []
    for band in bands:
        rect = band["_rect"]
        if blocks:
            last = blocks[-1]
            y_gap = rect.y0 - last["_rect"].y1
            x_overlap = min(rect.x1, last["_rect"].x1) - max(rect.x0, last["_rect"].x0)
            min_width = min(rect.width, last["_rect"].width)
            h_gap = max(rect.x0 - last["_rect"].x1, last["_rect"].x0 - rect.x1)
            # 纵向贴近，且要么横向重叠、要么水平方向紧邻（大运算符的上下限常挂在左侧）
            if y_gap < 14 and min_width > 0 and (x_overlap / min_width > 0.3 or h_gap < 40):
                last["_rect"] |= rect
                last["_texts"].extend(band["_texts"])
                continue
        blocks.append({"_rect": fitz.Rect(rect), "_texts": list(band["_texts"])})

    out: List[dict] = []
    for blk in blocks:
        r = blk["_rect"]
        text = " ".join(t for _, _, t in sorted(blk["_texts"], key=lambda item: (item[0], item[1])))
        out.append({
            "bbox": [round(r.x0 - 3, 2), round(r.y0 - 3, 2), round(r.x1 + 3, 2), round(r.y1 + 3, 2)],
            "text": text[:200],
        })

    # 去重可疑样本（同一字体同一字符集只留一条）
    dedup: dict = {}
    for s in suspects:
        dedup.setdefault((s["font"], s["chars"]), s)
    return out, list(dedup.values())


# ---------------------------------------------------------------------------
# 多栏布局检测与排序
# ---------------------------------------------------------------------------

def _column_clusters(
    blocks: List[dict], page_width: float, tolerance: float = 20.0
) -> List[List[dict]]:
    """按 x 坐标将文本块聚类为若干列，返回按阅读顺序排列的列列表。"""
    if not blocks:
        return []

    sorted_blocks = sorted(blocks, key=lambda b: b["bbox"][0])
    clusters = []
    current_cluster = [sorted_blocks[0]]
    current_x0 = sorted_blocks[0]["bbox"][0]

    for blk in sorted_blocks[1:]:
        x0 = blk["bbox"][0]
        if abs(x0 - current_x0) <= tolerance:
            current_cluster.append(blk)
        else:
            clusters.append(current_cluster)
            current_cluster = [blk]
            current_x0 = x0
    clusters.append(current_cluster)

    # 按阅读顺序排序列：左栏 → 右栏
    clusters.sort(key=lambda c: min(b["bbox"][0] for b in c))
    return clusters


def _extract_page_text(page, math_mode: bool = False) -> str:
    """从单页提取文本，自动处理多栏布局。

    math_mode=True 时用 _render_line_math 重建上下标（_{}/^{}）。
    """
    text_dict = page.get_text("dict")
    blocks = text_dict.get("blocks", [])

    # 只保留文本块
    text_blocks = [b for b in blocks if b.get("type") == 0 and b.get("lines")]
    if not text_blocks:
        return ""

    page_width = page.rect.width
    clusters = _column_clusters(text_blocks, page_width)

    page_text_parts: List[str] = []

    for col_blocks in clusters:
        col_blocks.sort(key=lambda b: b["bbox"][1])
        col_lines: List[str] = []
        for blk in col_blocks:
            for line in blk.get("lines", []):
                spans = line.get("spans", [])
                if math_mode:
                    line_text = _render_line_math(line)
                else:
                    line_text = "".join(s.get("text", "") for s in spans)
                if line_text.strip():
                    col_lines.append(line_text)
        if col_lines:
            page_text_parts.append("\n".join(col_lines))

    return "\n\n".join(page_text_parts)


# ---------------------------------------------------------------------------
# 元数据提取
# ---------------------------------------------------------------------------

def _extract_metadata(doc, file_path: str) -> dict:
    """从 PDF 文档提取元信息。"""
    meta = doc.metadata or {}
    file_stat = Path(file_path).stat()

    return {
        "file": str(Path(file_path).name),
        "file_size_mb": round(file_stat.st_size / (1024 * 1024), 2),
        "page_count": doc.page_count,
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "subject": meta.get("subject", ""),
        "keywords": meta.get("keywords", ""),
        "creator": meta.get("creator", ""),
        "producer": meta.get("producer", ""),
        "format": meta.get("format", ""),
        "creation_date": meta.get("creationDate", ""),
        "mod_date": meta.get("modDate", ""),
    }


# ---------------------------------------------------------------------------
# 主提取逻辑
# ---------------------------------------------------------------------------

def extract_pdf(
    pdf_path: str,
    pages_range: Tuple[int, int] | None = None,
    math_mode: bool = False,
) -> Tuple[str, dict, List[dict]]:
    """
    提取 PDF 全文及元数据。

    参数:
        pdf_path: PDF 文件路径
        pages_range: 可选 (start, end) 页码范围，1-indexed，含两端
        math_mode: 公式感知模式（重建上下标 + 定位公式块 + 字体诊断）

    返回:
        (full_text, metadata_dict, math_pages)
        math_pages 每项：{"page", "equations": [{"bbox", "text"}], "math_unreliable", "suspects"}
    """
    _load_fitz()
    doc = fitz.open(pdf_path)
    metadata = _extract_metadata(doc, pdf_path)

    total_pages = doc.page_count
    start_page = (pages_range[0] - 1) if pages_range else 0
    end_page = (pages_range[1]) if pages_range else total_pages

    start_page = max(0, start_page)
    end_page = min(total_pages, end_page)

    texts: List[str] = []
    empty_page_count = 0
    math_pages: List[dict] = []

    for i in range(start_page, end_page):
        page = doc[i]
        page_text = _extract_page_text(page, math_mode=math_mode)
        if not page_text.strip():
            empty_page_count += 1
            images = page.get_images()
            if images:
                page_text = (
                    f"[第 {i + 1} 页：扫描图像页，无文本层 — 含 {len(images)} 张图片]"
                )
        texts.append(f"--- 第 {i + 1} 页 ---\n{page_text}")

        if math_mode:
            equations, suspects = _page_equations(page)
            if equations or suspects:
                entry = {
                    "page": i + 1,
                    "equations": equations,
                    "math_unreliable": bool(suspects),
                }
                if suspects:
                    entry["suspects"] = suspects
                math_pages.append(entry)

    doc.close()

    full_text = _sanitize_text("\n\n".join(texts))
    metadata["empty_pages"] = empty_page_count
    metadata["is_scanned"] = empty_page_count >= total_pages * 0.8
    if math_mode:
        metadata["math_unreliable_pages"] = [
            p["page"] for p in math_pages if p["math_unreliable"]
        ]
        metadata["equation_blocks"] = sum(len(p["equations"]) for p in math_pages)

    return full_text, metadata, math_pages


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_page_range(arg: str) -> Tuple[int, int]:
    """解析 '1-5' 或 '3' 为 (start, end) 元组。"""
    if "-" in arg:
        parts = arg.split("-")
        return (int(parts[0]), int(parts[1]))
    else:
        page = int(arg)
        return (page, page)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用 PyMuPDF 提取 PDF 全文，自动处理多栏布局",
        epilog=f"中间产物目录（来自配置）：{_rel(tmp_dir())}",
    )
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="输出文件路径（推荐：写入文件可规避终端编码问题）",
    )
    parser.add_argument(
        "--json", action="store_true", help="以 JSON 格式输出（含元数据）"
    )
    parser.add_argument(
        "--pages", type=str, default=None, help="页码范围，如 '1-5' 或 '3'"
    )
    parser.add_argument(
        "--meta-only", action="store_true", help="仅输出元数据 JSON"
    )
    parser.add_argument(
        "--math",
        action="store_true",
        help="公式感知模式：重建上下标（_{}/^{}），并诊断数学字体映射错误",
    )
    parser.add_argument(
        "--equations-json",
        type=str,
        default=None,
        help="把公式块 bbox 与可靠性诊断写入该 JSON 文件（隐含 --math）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)

    math_mode = args.math or bool(args.equations_json)

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"错误：文件不存在 — {args.pdf_path}", file=sys.stderr)
        return 1

    if not pdf_path.suffix.lower() == ".pdf":
        print(f"错误：非 PDF 文件 — {args.pdf_path}", file=sys.stderr)
        return 1

    pages_range = parse_page_range(args.pages) if args.pages else None

    _load_fitz()  # 缺依赖时在这里打印安装指引并退出 1

    try:
        full_text, metadata, math_pages = extract_pdf(str(pdf_path), pages_range, math_mode)
    except Exception as e:
        print(f"错误：PDF 解析失败 — {e}", file=sys.stderr)
        return 1

    # ── 公式块 sidecar（供 crop_equations.py 裁剪）──
    if args.equations_json:
        import hashlib

        eq_doc = {
            "file": str(pdf_path),
            "source_sha256": hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest(),
            "coordinate_system": "PDF 点坐标，原点在左上角；渲染图像素 = 点 × (dpi / 72)",
            "pages": math_pages,
        }
        eq_path = Path(args.equations_json)
        if eq_path.parent and not eq_path.parent.exists():
            eq_path.parent.mkdir(parents=True, exist_ok=True)
        eq_path.write_text(json.dumps(eq_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[完成] 公式块 JSON 已写入 {eq_path.resolve()}", file=sys.stderr)

    # ── 构建输出内容 ──
    if args.meta_only:
        output_str = json.dumps(metadata, ensure_ascii=False, indent=2)
    elif args.json:
        output = {"metadata": metadata, "text": full_text}
        if math_mode:
            output["math_pages"] = math_pages
        output_str = json.dumps(output, ensure_ascii=False, indent=2)
    else:
        header = (
            f"# 文件: {metadata['file']}\n"
            f"# 页数: {metadata['page_count']}\n"
            f"# 标题: {metadata['title']}\n"
            f"# 作者: {metadata['author']}\n"
            f"# 扫描版: {'是' if metadata['is_scanned'] else '否'}\n"
            f"# 空页数: {metadata['empty_pages']}\n"
        )
        if math_mode:
            unreliable = metadata.get("math_unreliable_pages", [])
            header += (
                f"# 公式块: {metadata.get('equation_blocks', 0)}\n"
                f"# 公式不可靠页: {', '.join(str(p) for p in unreliable) if unreliable else '无'}"
                "（数学字体缺 ToUnicode，文本路径的符号可能失真 → 走视觉核对或取 arXiv 源）\n"
            )
        output_str = header + "\n" + full_text

    # ── 写入文件或 stdout ──
    if args.output:
        output_path = Path(args.output)
        if output_path.parent and not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_str, encoding="utf-8")
        print(f"[完成] 已写入 {output_path.resolve()} ({len(output_str)} 字符)", file=sys.stderr)
    else:
        # stdout 模式：已在 main() 顶部把 stdio 切到 UTF-8
        try:
            sys.stdout.write(output_str)
        except UnicodeEncodeError:
            # 终极兜底：将不可编码字符替换为 ?
            sys.stdout.write(output_str.encode("ascii", errors="replace").decode("ascii"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
