#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfcheck —— 环境 / 依赖 / 目录骨架 / 子脚本 /（可选）PDF 流水线的体检报告。

设计目标：**在任意机器上跑都不依赖任何硬编码路径** —— 工作区根、配置、目录、
解释器全部来自 `wiki_env`。默认无参数运行只做静态体检；想连 PDF 三件套一起验证，
用 `--pdf <path>` 显式给出输入 PDF。

用法：
    python .dsh/scripts/selfcheck.py                      # 体检报告（✓ / ✗ / –）
    python .dsh/scripts/selfcheck.py --pdf raw/papers/<paper>.pdf   # 附带 PDF 流水线回归
    python .dsh/scripts/selfcheck.py --json .dsh/tmp/selfcheck.json # 机器可读结果
    python .dsh/scripts/selfcheck.py --quiet              # 只输出一行结论

标记含义：
    ✓ 通过     ✗ 失败（必需项失败 → 退出码 1）     – 跳过 / 可选（不计入失败）

退出码：
    0  所有必需项通过（可选依赖、可选子脚本缺失不影响）
    1  有必需项失败
    2  用法错误

必需项：工作区与配置、目录骨架、Python 版本、存在的子脚本自检结论。
可选项：PyMuPDF、Pillow、项目 venv、LibreOffice Kit 渲染、网络取源、PDF 回归。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# ── 路径与编码：全仓唯一来源是 wiki_env ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import (  # noqa: E402
    CONFIG_PATH,
    WS,
    cfg,
    ensure_utf8_stdio,
    script_path,
    tmp_dir,
    vault_prefix,
    venv_python,
    wiki_dir,
    archive_dir,
    inbox_dir,
)

MIN_PYTHON = (3, 9)

PDF_INSTALL_HINT = (
    "  python -m venv .dsh/venv\n"
    "  # Windows:     .dsh\\venv\\Scripts\\python.exe -m pip install -r .dsh/requirements.txt\n"
    "  # macOS/Linux: .dsh/venv/bin/python -m pip install -r .dsh/requirements.txt"
)
KIT_HINT = "需先用 office-docx 技能取得 Kit 路径（本脚本不猜路径）"

OK, FAIL, SKIP = "ok", "fail", "skip"
MARK = {OK: "✓", FAIL: "✗", SKIP: "–"}

results: List[dict] = []


def record(name: str, status: str, detail: str = "", required: bool = True,
           extra: Optional[dict] = None) -> dict:
    item = {"name": name, "status": status, "detail": detail, "required": required}
    if extra:
        item.update(extra)
    results.append(item)
    return item


def check(name: str, ok: bool, detail: str = "", required: bool = True) -> dict:
    """二元判定：ok → ✓；否则 required 决定 ✗ 还是 –。"""
    status = OK if ok else (FAIL if required else SKIP)
    return record(name, status, detail, required)


def hint(text: str) -> None:
    """给最近一条结果挂上修复提示（在该项下方缩进打印，同时进 JSON）。"""
    lines = text.rstrip().splitlines()
    if results:
        results[-1].setdefault("hint", []).extend(lines)
    else:  # pragma: no cover - 只在前置记录之前调用时才会走到
        for line in lines:
            print(f"      {line}")


def print_item(item: dict) -> None:
    print(f"[{MARK[item['status']]}] {item['name']}"
          + (f" — {item['detail']}" if item["detail"] else ""))
    for line in item.get("hint", []):
        print(f"      {line}")


def run(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """统一子进程调用：UTF-8 + 捕获输出 + 不弹窗。"""
    return subprocess.run(
        [str(c) for c in cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd or WS),
    )


def tail_lines(text: str, limit: int = 3) -> str:
    """取输出的关键行（尾部非空行），用于把子脚本结论带回报告。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return " ⏎ ".join(lines[-limit:])


def _rel(path: Path) -> str:
    try:
        return path.relative_to(WS).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# 1. 工作区与配置
# ---------------------------------------------------------------------------

def check_workspace() -> None:
    check("工作区根存在", WS.is_dir(), str(WS), required=True)
    if not CONFIG_PATH.exists():
        record("配置文件可解析", FAIL, f"缺失 {_rel(CONFIG_PATH)}", True)
        hint("配置缺失时脚本会退回内置默认值，但建议恢复该文件（见仓库内的配置模板）。")
        return
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("根节点必须是 JSON 对象")
        # 不把 `$comment*` 之类的说明键算作配置项，否则键数会虚高
        n_real = sum(1 for k in raw if not str(k).startswith("$"))
        check("配置文件可解析", True, f"{_rel(CONFIG_PATH)}（{n_real} 个配置键）")
    except Exception as exc:
        record("配置文件可解析", FAIL, f"{_rel(CONFIG_PATH)}：{exc}", True)
        hint("修正 JSON 语法后重跑；解析失败时脚本会退回内置默认配置。")
        return
    vp = vault_prefix()
    record("vault_prefix 解析", OK,
           f'"{vp}"' + ("（工作区即库根）" if vp == "" else "（写进 .canvas 的路径需带此前缀）"))


# ---------------------------------------------------------------------------
# 2. 目录骨架
# ---------------------------------------------------------------------------

def skeleton_targets() -> List[tuple]:
    """返回 [(显示名, 路径, 是否为目录, 必需)]，全部来自配置。"""
    targets: List[tuple] = []
    wiki_root = wiki_dir()
    targets.append((_rel(wiki_root) + "/", wiki_root, True, True))
    for sub in (cfg("wiki_types", default={}) or {}).keys():
        p = wiki_dir(sub)
        targets.append((_rel(p) + "/", p, True, True))

    raw_root = Path(cfg("dirs", "raw", default="raw"))
    raw_root = raw_root if raw_root.is_absolute() else WS / raw_root
    targets.append((_rel(raw_root) + "/", raw_root, True, True))
    targets.append((_rel(inbox_dir()) + "/", inbox_dir(), True, True))
    for kind in (cfg("dirs", "archive", default={}) or {}).keys():
        p = archive_dir(kind)
        targets.append((_rel(p) + "/", p, True, True))

    for key in ("index", "log", "tags_doc"):
        rel = cfg("files", key, default=None)
        if rel:
            p = Path(rel)
            p = p if p.is_absolute() else WS / p
            targets.append((_rel(p), p, False, True))

    # 非知识页目录：缺失不算失败，只提示
    for key in ("my_research", "weekly"):
        rel = cfg("dirs", key, default=None)
        if rel:
            p = Path(rel)
            p = p if p.is_absolute() else WS / p
            targets.append((_rel(p) + "/", p, True, False))
    return targets


def check_skeleton() -> None:
    first_missing = None
    for label, path, is_dir, required in skeleton_targets():
        exists = path.is_dir() if is_dir else path.is_file()
        item = check(f"骨架 {label}", exists, "" if exists else "缺失", required=required)
        if not exists and required and first_missing is None:
            first_missing = item
    if first_missing is not None:
        first_missing.setdefault("hint", []).append(
            "修复：python .dsh/scripts/setup_wiki.py   （幂等，只补齐缺失的目录与文件）")


# ---------------------------------------------------------------------------
# 3. 解释器与可选依赖
# ---------------------------------------------------------------------------

def find_spec_safe(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def check_python() -> None:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    check(f"Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
          ok, f"{v.major}.{v.minor}.{v.micro} @ {sys.executable}")
    if not ok:
        hint("升级解释器后重跑：本工具包使用 f-strings 与 `from __future__ import annotations`，"
             "最低 Python 3.9。")


def check_optional_deps() -> None:
    has_mupdf = find_spec_safe("pymupdf") or find_spec_safe("fitz")
    record("可选依赖 pymupdf（PDF 正文抽取）", OK if has_mupdf else SKIP,
           "已安装" if has_mupdf else "未安装 — extract_pdf.py 与 --pdf 回归不可用",
           required=False)
    if not has_mupdf:
        hint("安装（投影到项目 venv，不要装进系统 Python）：")
        hint(PDF_INSTALL_HINT)

    has_pil = find_spec_safe("PIL")
    record("可选依赖 Pillow（公式小图裁剪）", OK if has_pil else SKIP,
           "已安装" if has_pil else "未安装 — crop_equations.py 不可用", required=False)
    if not has_pil:
        hint("安装：")
        hint(PDF_INSTALL_HINT)


def check_venv() -> None:
    vpy = venv_python()
    record("项目 venv（.dsh/venv）", OK if vpy else SKIP,
           _rel(vpy) if vpy else "未创建 — 只有 PDF 正文抽取需要它，其它脚本用 harness 自带 Python 即可",
           required=False)
    if not vpy:
        hint("需要时创建：")
        hint(PDF_INSTALL_HINT)


def pdf_capable_python() -> Optional[str]:
    """挑一个能 `import pymupdf` 的解释器：优先当前解释器，其次项目 venv。"""
    seen: List[str] = []
    for cand in (sys.executable, str(venv_python() or "")):
        if cand and cand not in seen:
            seen.append(cand)
    for exe in seen:
        try:
            r = run([exe, "-c", "import pymupdf"])
        except OSError:
            continue
        if r.returncode == 0:
            return exe
    return None


# ---------------------------------------------------------------------------
# 4. 子脚本自检（子进程调用；脚本不存在就标 –）
# ---------------------------------------------------------------------------

def check_subscripts() -> None:
    for name in ("tag_vocab.py", "gen_canvas.py"):
        path = script_path(name)
        if not path.exists():
            record(f"子脚本 {name} --check", SKIP, "脚本不存在（可能尚未提供）", required=False)
            continue
        r = run([sys.executable, _rel(path), "--check"])
        detail = tail_lines(r.stdout) or tail_lines(r.stderr) or "(无输出)"
        if r.returncode != 0:
            err = tail_lines(r.stderr, 2)
            if err:
                detail = f"{detail} | stderr: {err}"
        check(f"子脚本 {name} --check", r.returncode == 0,
              f"rc={r.returncode} | {detail}", required=True)
        if r.returncode != 0 and name == "gen_canvas.py":
            hint("画布缺失或过期时：先跑 `python .dsh/scripts/setup_wiki.py` 补齐；")
            hint("族结构确实变了就重生成：`python .dsh/scripts/gen_canvas.py`。")


# ---------------------------------------------------------------------------
# 5. 可选：PDF 流水线回归（只在给出 --pdf 时跑）
# ---------------------------------------------------------------------------
#
# 覆盖点（沿用自旧的回归脚本，去掉全部硬编码）：
#   ① arXiv/DOI 识别 + 有源取 LaTeX / 无源优雅降级
#   ② --math 上下标重建、公式块 bbox、数学字体不可靠页诊断
#   ③ bbox → 像素换算裁剪（渲染用 PyMuPDF，Kit 缺失不猜路径）
#   ④ 扫描版（图像 PDF）识别
#   ⑤ 无 venv 情况：不依赖 PyMuPDF 的脚本仍能独立运行

ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(v\d+)?", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")


def pdf_regression(pdf: Path, exe: str, note: List[str]) -> None:
    """跑 PDF 三件套回归。结果通过 record()/check() 追加进全局 results。"""
    base = tmp_dir() / "selfcheck"
    base.mkdir(parents=True, exist_ok=True)
    src_script = _rel(script_path("fetch_source.py"))
    ext_script = _rel(script_path("extract_pdf.py"))
    crop_script = _rel(script_path("crop_equations.py"))

    # ── ① 源识别 + 取源 ──────────────────────────────────────────────
    head = ""
    try:
        r = run([exe, "-c",
                 "import pymupdf,sys;d=pymupdf.open(sys.argv[1]);"
                 "print(''.join(d[i].get_text() for i in range(min(2,d.page_count))));d.close()",
                 str(pdf)])
        head = r.stdout or ""
    except OSError as exc:
        note.append(f"首页文本读取失败：{exc}")
    m_arxiv = ARXIV_RE.search(head)
    m_doi = DOI_RE.search(head)
    arxiv_id = (m_arxiv.group(1) + (m_arxiv.group(2) or "")) if m_arxiv else ""
    doi = m_doi.group(1) if m_doi else ""
    check("PDF ① 首页识别出 arXiv ID / DOI", bool(arxiv_id or doi),
          f"arXiv={arxiv_id or '—'} DOI={doi or '—'}", required=False)

    src_md = base / "source.md"
    r = run([exe, src_script, "--from-pdf", str(pdf), "-o", str(src_md)])
    text = src_md.read_text(encoding="utf-8") if src_md.exists() else ""
    n_formulas = len(re.findall(r"^[0-9]+[.] [$]", text, re.M))
    if arxiv_id or doi:
        if r.returncode == 0 and n_formulas:
            check("PDF ① 取源拿到 LaTeX 公式真值", True, f"{n_formulas} 条", required=False)
        else:
            record("PDF ① 取源拿到 LaTeX 公式真值", SKIP,
                   f"rc={r.returncode}（多为网络不可用，非环境问题）", required=False)
            note.append("取源未成功：若本机离线，此步属正常跳过。")
    else:
        check("PDF ① 无源论文取源脚本优雅退出（rc=3）", r.returncode == 3,
              f"rc={r.returncode}", required=False)

    # ── ② 文本路径：--math ──────────────────────────────────────────
    out_txt = base / "text.txt"
    eq_json = base / "equations.json"
    r = run([exe, ext_script, str(pdf), "--math", "--equations-json", str(eq_json),
             "-o", str(out_txt)])
    body = out_txt.read_text(encoding="utf-8") if out_txt.exists() else ""
    data = {}
    if eq_json.exists():
        try:
            data = json.loads(eq_json.read_text(encoding="utf-8"))
        except Exception as exc:
            note.append(f"sidecar 解析失败：{exc}")
    pages = data.get("pages", []) or []
    n_blocks = sum(len(p.get("equations", [])) for p in pages)
    check("PDF ② 文本路径 --math 成功", r.returncode == 0 and bool(body),
          f"rc={r.returncode}, {len(body)} 字符", required=False)
    check("PDF ② 上下标被重建（_{} / ^{}）", ("_{" in body or "^{" in body),
          "命中" if ("_{" in body or "^{" in body) else "正文未出现上下标标记",
          required=False)
    check("PDF ② 公式块 bbox 产出", n_blocks >= 1,
          f"{len(pages)} 页命中，共 {n_blocks} 块", required=False)
    check("PDF ② sidecar 带 sha256 与坐标约定",
          bool(data.get("source_sha256")) and "dpi" in (data.get("coordinate_system") or ""),
          (data.get("coordinate_system") or "缺少 coordinate_system")[:48],
          required=False)
    unreliable = [p["page"] for p in pages if p.get("math_unreliable")]
    record("PDF ② 不可靠页诊断（数学字体缺 ToUnicode）",
           OK if unreliable else SKIP,
           f"标记页 {unreliable}" if unreliable else "本 PDF 未命中该特征（非缺陷）",
           required=False)

    # ── ③ bbox → 像素 裁剪（Kit 缺省时不猜路径，用 PyMuPDF 渲染代替）──
    record("PDF ③ LibreOffice Kit 渲染", SKIP, KIT_HINT, required=False)
    page_with_eq = next((p for p in pages if p.get("equations")), None)
    if page_with_eq is None:
        record("PDF ③ bbox 裁剪换算", SKIP, "本 PDF 没有可用公式块，跳过", required=False)
    else:
        pno = int(page_with_eq["page"])
        render_dir = base / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        png = render_dir / f"page-{pno}.png"
        dpi = 200  # PyMuPDF 的 get_pixmap(dpi=) 只接受整数
        r = run([exe, "-c",
                 "import pymupdf,sys;d=pymupdf.open(sys.argv[1]);"
                 "p=d[int(sys.argv[3])-1];"
                 "p.get_pixmap(dpi=int(float(sys.argv[4]))).save(sys.argv[2]);d.close()",
                 str(pdf), str(png), str(pno), str(dpi)])
        if r.returncode != 0 or not png.exists():
            record("PDF ③ bbox 裁剪换算", SKIP,
                   f"渲染页图失败（rc={r.returncode}）：{tail_lines(r.stderr, 1)}", required=False)
        else:
            pypdf = run([exe, "-c",
                         "import pymupdf,sys;d=pymupdf.open(sys.argv[1]);"
                         "p=d[int(sys.argv[2])-1];print(p.rect.width,p.rect.height);d.close()",
                         str(pdf), str(pno)])
            try:
                pw, ph = (float(x) for x in pypdf.stdout.split()[:2])
            except Exception:
                pw, ph = (0.0, 0.0)
            kinds = {
                "96dpi 单位": {"x": 0.0, "y": 0.0,
                               "width": pw * 96.0 / 72.0, "height": ph * 96.0 / 72.0},
                "PDF 点": {"x": 0.0, "y": 0.0, "width": pw, "height": ph},
            }
            made = 0
            max_crop = 0
            for label, rect in kinds.items():
                slug = "96" if label.startswith("96") else "pt"
                man = render_dir / f"manifest-{slug}.json"
                man.write_text(json.dumps(
                    {"dpi": dpi,
                     "images": [{"page": pno, "path": str(png), "rectangle": rect}]},
                    ensure_ascii=False, indent=2), encoding="utf-8")
                crops_dir = base / f"crops-{slug}"
                rr = run([exe, crop_script, "--manifest", str(man), "--equations", str(eq_json),
                          "--out-dir", str(crops_dir)])
                idx = crops_dir / "equations_index.json"
                crops = []
                if idx.exists():
                    try:
                        crops = json.loads(idx.read_text(encoding="utf-8")).get("crops", [])
                    except Exception:
                        crops = []
                made += len(crops)
                max_crop = max([max_crop] + [c["bytes"] for c in crops])
                check(f"PDF ③ 裁剪换算（rectangle = {label}）",
                      rr.returncode == 0 and len(crops) >= 1,
                      f"rc={rr.returncode}, {len(crops)} 张", required=False)
            page_kb = png.stat().st_size / 1024
            check("PDF ③ 公式小图远小于整页",
                  made > 0 and (max_crop / 1024) < page_kb / 3,
                  f"最大裁剪 {max_crop / 1024:.1f} KB vs 整页 {page_kb:.0f} KB",
                  required=False)

    # ── ④ 扫描版（图像 PDF）识别 ────────────────────────────────────
    # 注意：产物名不能和输入 PDF 撞名（PyMuPDF 不允许保存到已打开的同一文件）
    scanned = base / "image-only.pdf"
    if pdf.resolve() == scanned.resolve():
        scanned = base / "image-only-2.pdf"
    r = run([exe, "-c",
             "import pymupdf,sys;d=pymupdf.open(sys.argv[1]);"
             "src=d[0];pix=src.get_pixmap(dpi=100);pix.save(sys.argv[2]);"
             "out=pymupdf.open();pg=out.new_page(width=src.rect.width,height=src.rect.height);"
             "pg.insert_image(pg.rect,filename=sys.argv[2]);out.save(sys.argv[3]);out.close();d.close()",
             str(pdf), str(base / "page0.png"), str(scanned)])
    if r.returncode == 0 and scanned.exists():
        sc_txt = base / "scanned.txt"
        r2 = run([exe, ext_script, str(scanned), "-o", str(sc_txt)])
        sc = sc_txt.read_text(encoding="utf-8") if sc_txt.exists() else ""
        check("PDF ④ 扫描/图像版被识别", r2.returncode == 0 and "# 扫描版: 是" in sc,
              f"rc={r2.returncode}", required=False)
    else:
        record("PDF ④ 扫描/图像版被识别", SKIP,
               f"未能构造图像 PDF（rc={r.returncode}）", required=False)

    # ── ⑤ 无 venv 依赖声明：不依赖 PyMuPDF 的脚本可独立运行 ──────────
    for name in ("fetch_source.py", "crop_equations.py"):
        path = script_path(name)
        if not path.exists():
            record(f"PDF ⑤ {name} 顶层不依赖 PyMuPDF", SKIP, "脚本不存在", required=False)
            continue
        src = path.read_text(encoding="utf-8")
        top_import = re.search(r"^import pymupdf|^import fitz", src, re.M)
        check(f"PDF ⑤ {name} 顶层不依赖 PyMuPDF", top_import is None,
              "只需标准库/Pillow 即可运行" if top_import is None else "存在顶层导入",
              required=False)
    venv_note = "已装 venv" if venv_python() else "无 venv（本次用 harness 自带 Python 跑通）"
    record("PDF ⑤ 解释器", OK, f"{exe}（{venv_note}）", required=False)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="selfcheck.py",
        description="环境 / 依赖 / 目录骨架 / 子脚本 /（可选）PDF 流水线体检",
        epilog="必需项失败 → 退出码 1；可选依赖缺失只标 –，不影响退出码。",
    )
    p.add_argument("--pdf", default=None,
                   help="给一个 PDF 路径则额外跑 PDF 流水线回归（不给则跳过）")
    p.add_argument("--json", dest="json_path", default=None, help="机器可读结果输出路径")
    p.add_argument("--quiet", action="store_true", help="只输出一行结论")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)

    if not args.quiet:
        print(f"== selfcheck：{WS} ==")
        print(f"   解释器 {sys.executable}")
        print()

    # 1–5. 静态体检
    check_workspace()
    check_skeleton()
    check_python()
    check_optional_deps()
    check_venv()
    check_subscripts()

    notes: List[str] = []
    pdf_summary = None
    if args.pdf:
        pdf = Path(args.pdf)
        if not pdf.is_absolute():
            pdf = (Path.cwd() / pdf).resolve()
        exe = pdf_capable_python()
        if not pdf.is_file():
            record("PDF 流水线回归", FAIL, f"文件不存在：{args.pdf}", required=False)
        elif exe is None:
            record("PDF 流水线回归", SKIP,
                   "没有能 `import pymupdf` 的解释器，跳过（安装指引见上）", required=False)
        else:
            if not args.quiet:
                print(f"-- PDF 流水线回归：{pdf.name}（解释器 {exe}）--")
            before = len(results)
            pdf_regression(pdf, exe, notes)
            section = results[before:]
            if not args.quiet:
                for item in section:
                    print_item(item)
                print()
            pdf_summary = {
                "path": str(pdf),
                "interpreter": exe,
                "ok": sum(1 for i in section if i["status"] == OK),
                "fail": sum(1 for i in section if i["status"] == FAIL),
                "skip": sum(1 for i in section if i["status"] == SKIP),
            }
    else:
        record("PDF 流水线回归", SKIP, "未提供 --pdf，跳过 PDF 流水线回归", required=False)
        if not args.quiet:
            print("[–] 未提供 --pdf，跳过 PDF 流水线回归")
            print()

    # ── 报告 ──
    if not args.quiet:
        print("-- 体检结果 --")
        for item in results:
            print_item(item)
        print()

    n_ok = sum(1 for i in results if i["status"] == OK)
    n_fail = sum(1 for i in results if i["status"] == FAIL)
    n_skip = sum(1 for i in results if i["status"] == SKIP)
    req_failed = [i["name"] for i in results if i["required"] and i["status"] == FAIL]
    code = 1 if req_failed else 0

    if not args.quiet:
        if req_failed:
            print("-- 必需项失败 --")
            for name in req_failed:
                print(f"  ✗ {name}")
            print()
        for msg in notes:
            print(f"  注：{msg}")
        if notes:
            print()

    summary = (f"selfcheck: ✓{n_ok} ✗{n_fail} –{n_skip}"
               f"，必需项{'全部通过' if code == 0 else f'失败 {len(req_failed)} 项'} → exit {code}")
    print(summary)

    if args.json_path:
        payload = {
            "workspace": str(WS),
            "config_path": str(CONFIG_PATH),
            "vault_prefix": vault_prefix(),
            "python": sys.executable,
            "python_version": ".".join(str(x) for x in sys.version_info[:3]),
            "venv_python": str(venv_python()) if venv_python() else None,
            "checks": results,
            "pdf": pdf_summary,
            "notes": notes,
            "summary": {
                "ok": n_ok, "fail": n_fail, "skip": n_skip,
                "required_failed": req_failed, "exit_code": code,
            },
        }
        out = Path(args.json_path)
        if not out.is_absolute():
            out = (Path.cwd() / out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"[json] {out}")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
