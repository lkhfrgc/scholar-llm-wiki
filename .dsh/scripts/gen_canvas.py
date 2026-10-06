#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 / 校验概念 Canvas（全库总图 + 单族图）。

用法：
    python .dsh/scripts/gen_canvas.py           # 重新生成全部画布（总图 + 每个母页一张族图）
    python .dsh/scripts/gen_canvas.py --check   # 只校验：对比画布内记录的「结构指纹」与当前 wiki 结构

输出位置与标题全部来自 `.dsh/wiki.config.json`：
`canvas.overview` 是总图，`canvas.family_prefix + <母页名> + .canvas` 是单族图，
标题卡首行是 `<wiki_name> · <canvas.title>`。脚本从工作区任意目录都能跑（路径全走 `wiki_env`）。

退出码：0 = 无问题；1 = 有画布缺失或过期（`--check`）；2 = 用法错误。

设计要点（与 AGENTS.md「概念分层」「Canvas 同步」一致）：
  * 画布卡片一律使用 text 节点 + [[页面名]]（文本链接），**不使用 file 节点**——避免 Obsidian 嵌入笔记正文导致渲染开销过大
  * 母页 tag=`母概念`、子页 tag=`子概念`、母页 `## 子概念` 段决定分组、子页文首定位行决定多父
  * 每张画布标题卡内写入「结构指纹 <8位十六进制>」；族结构变化后指纹失配 → --check 报 STALE
  * 万一画布里出现 `file` 字段，一律经 `vault_rel()` 规范成**库根相对路径**：
    Obsidian 的 `file` 按路径解析（不像 `[[双链]]` 按文件名解析），漏掉库根前缀就会显示「未找到引用的文件」
"""
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

# 同目录的共享路径层：本仓库内唯一允许"找路径"的地方，禁止再写绝对路径
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, cfg, ensure_utf8_stdio, vault_prefix, vault_rel, wiki_dir  # noqa: E402


def _wiki_subdir_for(type_name, fallback):
    """按 `wiki_types`（wiki 子目录名 → frontmatter 的 type 值）反查子目录。

    配置里改了目录名（例如 concepts → 概念）本脚本无需改动；
    表里没有对应 type 时回退到 `fallback`，保证脚本不会因为缺键直接崩。
    """
    for sub, t in (cfg("wiki_types", default={}) or {}).items():
        if t == type_name:
            return wiki_dir(sub)
    return wiki_dir(fallback)


CON = _wiki_subdir_for("concept", "concepts")   # 概念页目录
PAP = _wiki_subdir_for("paper", "papers")       # 论文页目录（用来找"实例化本族"的论文）
WROOT = wiki_dir()                              # wiki/ 根，画布落在这里之外的话由配置决定
CW, CH, MW, MH, PW, PH, GAP = 236, 56, 340, 78, 240, 48, 14
GEN_VERSION = "v2"  # 生成器版本：升级即让全部画布指纹失配，强制重新生成
FP_RE = re.compile(r"结构指纹 ([0-9a-f]{8})")


def _ws_path(rel):
    """配置里的相对路径 → 工作区内的路径（已是绝对路径则原样返回）。"""
    q = Path(rel)
    return q if q.is_absolute() else WS / q


def overview_path():
    """总图路径 = `WS / cfg("canvas","overview")`。"""
    return _ws_path(cfg("canvas", "overview", default="wiki/概念全景图.canvas"))


def family_path(mother):
    """单族图路径 = `WS / (cfg("canvas","family_prefix") + 母页名 + ".canvas")`。"""
    return _ws_path("%s%s.canvas" % (cfg("canvas", "family_prefix", default="wiki/概念地图-"), mother))


def rd(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def md_names(d):
    """目录下的 .md 文件名；目录不存在时返回空列表（空库也能跑 --check，不抛栈）。"""
    try:
        return sorted(fn for fn in os.listdir(d) if fn.endswith(".md"))
    except OSError:
        return []


LINKS = lambda s: re.findall(r"\[\[([^\[\]\|]+?)\]\]", s)


def strip_md(s):
    return re.sub(r"\$([^$]*)\$", r"\1", s).replace("**", "").replace("`", "").strip()


def section(t, title):
    m = re.search(r"(?ms)^##\s*" + re.escape(title) + r"\s*$(.*?)(?=^##\s|\Z)", t)
    return m.group(1) if m else ""


def load_pages():
    pages = {}
    for fn in md_names(CON):
        t = rd(os.path.join(CON, fn))
        nm = fn[:-3]
        tags = ""
        m = re.search(r"(?m)^tags:\s*\[([^\]]*)\]", t)
        if m:
            tags = m.group(1)
        else:
            m2 = re.search(r"(?ms)^tags:\s*\r?\n((?:\s*-\s*.+\r?\n)+)", t)
            if m2:
                tags = ",".join(x.strip(" -\r\n") for x in m2.group(1).split("\n") if x.strip())
        par = []
        mp = re.search(r"(?m)^>\s*\*\*母概念\*\*：(.+)$", t)
        if mp:
            par = LINKS(mp.group(1))
        pages[nm] = {"t": t, "mother": bool(re.match(r"母概念(\s*,|$)", tags.strip())), "parents": par}
    return pages


def parse_groups(t):
    sub = section(t, "子概念")
    groups = []
    if re.search(r"(?m)^###\s", sub):
        parts = re.split(r"(?m)^###\s*(.+)$", sub)
        for i in range(1, len(parts), 2):
            items = []
            for ln in parts[i + 1].split("\n"):
                m2 = re.match(r"^\s*-\s*(.*)$", ln)
                if not m2:
                    continue
                head, _, desc = m2.group(1).partition("—")
                for c in LINKS(head):
                    items.append((c, strip_md(desc)))
            if items:
                groups.append((parts[i].strip(), items))
    else:
        items = []
        for ln in sub.split("\n"):
            m2 = re.match(r"^\s*-\s*(.*)$", ln)
            if not m2:
                continue
            head, _, desc = m2.group(1).partition("—")
            for c in LINKS(head):
                items.append((c, strip_md(desc)))
        if items:
            groups.append(("子概念", items))
    return groups


def fam_fingerprint(mo, pages):
    kids = sorted({c for _, items in parse_groups(pages[mo]["t"]) for c, _ in items})
    raw = GEN_VERSION + "|" + mo + "|" + "|".join(k + ":" + ",".join(sorted(pages.get(k, {}).get("parents", []))) for k in kids)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]


def wrap_cn(s, w, fs):
    per = max(6, int(w / (fs * 0.62)))
    out, cur = [], ""
    for ch in s:
        cur += ch
        if len(cur) >= per:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def TC(i, x, y, w, h, text, color=None):
    d = {"id": i, "type": "text", "text": text, "x": int(x), "y": int(y), "width": int(w), "height": int(h)}
    if color:
        d["color"] = color
    return d


def GP(i, x, y, w, h, label):
    return {"id": i, "type": "group", "label": label, "x": int(x), "y": int(y), "width": int(w), "height": int(h), "color": "4"}


def link_card(nm, color):
    return "**[[%s]]**" % nm if color == "6" else "[[%s]]" % nm


def build_family(mo, pages, papers, fp):
    t = pages[mo]["t"]
    nodes, edges, ctr = [], [], [0]

    def nid(pfx):
        ctr[0] += 1
        return "%s%d" % (pfx, ctr[0])

    tm = re.search(r'(?m)^title:\s*"?(.+?)"?\s*$', t)
    title = tm.group(1) if tm else mo
    summary = " ".join(l for l in strip_md(section(t, "这一族的地图")).split("\n") if l.strip())[:340]
    groups = parse_groups(t)
    rel = []
    for ln in section(t, "关联连接").split("\n"):
        m2 = re.match(r"^\s*-\s*(.*)$", ln)
        if not m2:
            continue
        head, _, desc = m2.group(1).partition("：")
        for c in LINKS(head):
            rel.append((c, strip_md(desc)))
    qs = [strip_md(l.strip(" -")) for l in section(t, "开放问题").split("\n") if l.strip().startswith("-")]
    fam = {mo} | {c for _, items in groups for c, _ in items}
    plist = [p for _, p in sorted(((len(papers[p] & fam), p) for p in papers if len(papers[p] & fam) >= 2), reverse=True)[:12]]
    nodes.append(TC("title", 0, 0, 1000, 120,
                    "# %s\n`#母概念` ｜ 子页 %d · 分组 %d ｜ 结构指纹 %s" % (title, sum(len(g[1]) for g in groups), len(groups), fp)))
    nodes.append(TC("summary", 0, 140, 1000, 200, "**这一族的地图**\n\n" + summary))
    mid = "mother"
    nodes.append(TC(mid, 300, 370, MW, MH, link_card(mo, "6"), "6"))
    row_x, row_y, row_h = 0, 520, 0
    SH = 32
    for gl, items in groups:
        cols = min(3, max(1, len(items)))
        rows = math.ceil(len(items) / cols)
        gw = max(cols * CW + (cols - 1) * GAP, 720) + 60
        dl = []
        for c, d in items:
            dl += wrap_cn(("· %s：%s" % (c, d)) if d else ("· " + c), gw - 90, 12)
        dh = 24 + len(dl) * 17
        # 多父子页：在框内底部插入「其他父页」占位卡（逐条列出本族之外的父页）
        stubs = [(c, [p for p in pages.get(c, {}).get("parents", []) if p != mo]) for c, _ in items]
        stubs = [(c, o) for c, o in stubs if o]
        gh = 52 + rows * CH + (rows - 1) * GAP + 20 + dh + 24 + (len(stubs) * (SH + 10) + 16 if stubs else 0)
        if row_x + gw > 2900:
            row_x, row_y, row_h = 0, row_y + row_h + 60, 0
        nodes.append(GP(nid("g"), row_x, row_y, gw, gh, "%s（%d）" % (gl, len(items))))
        card_id = {}
        for k, (c, d) in enumerate(items):
            cc, rr = k % cols, k // cols
            multi = len(pages.get(c, {}).get("parents", [])) > 1
            cid = nid("c")
            card_id[c] = cid
            nodes.append(TC(cid, row_x + 30 + cc * (CW + GAP), row_y + 52 + rr * (CH + GAP), CW, CH,
                            link_card(c, "2" if multi else "5"), "2" if multi else "5"))
            prim = (not pages.get(c, {}).get("parents")) or pages[c]["parents"][0] == mo
            edges.append({"id": nid("e"), "fromNode": mid, "fromSide": "bottom", "toNode": cid, "toSide": "top",
                          "label": "子概念" if prim else "多父", "color": "5" if prim else "2"})
        nodes.append(TC(nid("d"), row_x + 30, row_y + 52 + rows * CH + (rows - 1) * GAP + 20, gw - 60, dh, "\n".join(dl)))
        sy = row_y + 52 + rows * CH + (rows - 1) * GAP + 20 + dh + 16
        for c, others in stubs:
            sid = nid("s")
            nodes.append(TC(sid, row_x + 30, sy, gw - 60, SH,
                            "↳ [[%s]] 的其他父页：%s" % (c, "、".join("[[%s]]" % o for o in others)), "2"))
            edges.append({"id": nid("e"), "fromNode": card_id[c], "fromSide": "bottom", "toNode": sid, "toSide": "top",
                          "label": "多父", "color": "2"})
            sy += SH + 10
        row_x += gw + 60
        row_h = max(row_h, gh)
    RX, RW, ry = 3000, 780, 140
    rl = ["· [[%s]]" % c + (("：" + d) if d else "") for c, d in rel]
    rh = 40 + (len(rl) if rl else 1) * 17 + 16
    nodes.append(TC("rel", RX, ry, RW, rh, "**关联连接**（跨族桥）\n\n" + "\n".join(rl)))
    ry += rh + 70
    ql = []
    for q in qs:
        ql += wrap_cn("· " + q, RW - 30, 12)
    qh = 40 + len(ql) * 17 + 16
    nodes.append(TC("qs", RX, ry, RW, qh, "**开放问题**\n\n" + "\n".join(ql)))
    ry += qh + 70
    if plist:
        rows = math.ceil(len(plist) / 2)
        gh = 52 + rows * (PH + GAP) + 16
        nodes.append(GP("papers", RX, ry, RW, gh, "实例化本族的论文（与族内 ≥2 页相关，Top %d）" % len(plist)))
        for k, p in enumerate(plist):
            cc, rr = k % 2, k // 2
            nodes.append(TC(nid("p"), RX + 30 + cc * (PW + 16), ry + 52 + rr * (PH + GAP), PW, PH, "[[%s]]" % p, "1"))
    return {"nodes": nodes, "edges": edges}


def build_atlas(mothers, pages, fps):
    nodes, edges, ctr = [], [], [0]

    def nid(pfx):
        ctr[0] += 1
        return "%s%d" % (pfx, ctr[0])

    fam = []
    for mo in mothers:
        kids = [c for _, items in parse_groups(pages[mo]["t"]) for c, _ in items]
        n = len(kids)
        cols = max(1, n) if n <= 3 else (2 if n <= 6 else 3)
        rows = math.ceil(n / cols) if n else 1
        gw = max(cols * CW + (cols - 1) * GAP, MW) + 60
        gh = 52 + MH + 20 + rows * CH + (rows - 1) * GAP + 26
        fam.append((mo, kids, cols, rows, gw, gh))
    colW, rowH = [0, 0, 0], [0, 0, 0]
    for i, f in enumerate(fam):
        c, r = i % 3, i // 3
        colW[c] = max(colW[c], f[4])
        rowH[r] = max(rowH[r], f[5])
    colX = [0, colW[0] + 90, colW[0] + colW[1] + 180]
    rowY = [0, rowH[0] + 90, rowH[0] + rowH[1] + 180]
    uniq = {c for _, kids, _, _, _, _ in fam for c in kids}
    nedge = sum(len(f[1]) for f in fam)
    gfp = hashlib.sha1((GEN_VERSION + "|" + "|".join(fps[m] for m in sorted(fps))).encode("utf-8")).hexdigest()[:8]
    # 标题不写死库名：库名与画布标题都来自配置（换库/改名后无需改脚本）
    wiki_name = cfg("wiki_name", default="LLM Wiki")
    canvas_title = cfg("canvas", "title", default="概念全景图")
    nodes.append(TC("title", 0, 0, 900, 130,
                    "# %s · %s\n%d 族母页 ｜ %d 个子页 ｜ 层级边 %d 条 ｜ 结构指纹 %s" % (
                        wiki_name, canvas_title, len(fam), len(uniq), nedge, gfp)))
    nodes.append(TC("legend", 940, 0, 620, 250,
                    "**图例**\n\n- 紫卡 = 母概念页（tag `母概念`）\n- 青卡 = 子概念页（tag `子概念`）\n"
                    "- 橙卡 = 多父子页（属于 ≥2 个族）\n- 绿框 = 族分组\n"
                    "- 边 `子概念` = 主父；边 `多父` = 第二/第三个父页（**多父子页与其所有父页相连**：框内边 + 跨族边）\n\n"
                    "> 卡片均为**文本链接**（Obsidian 双链语法），点击可跳转；**不嵌入笔记正文**，渲染开销低。"))
    mid_of, cross = {}, []
    for i, (mo, kids, cols, rows, gw, gh) in enumerate(fam):
        gx, gy = colX[i % 3], rowY[i // 3] + 320
        nodes.append(GP(nid("g"), gx, gy, gw, gh, "%s（%d 子页）" % (mo, len(kids))))
        mid = nid("m")
        nodes.append(TC(mid, gx + (gw - MW) // 2, gy + 52, MW, MH, link_card(mo, "6"), "6"))
        for k, c in enumerate(kids):
            cc, rr = k % cols, k // cols
            multi = len(pages.get(c, {}).get("parents", [])) > 1
            cid = nid("c")
            nodes.append(TC(cid, gx + 30 + cc * (CW + GAP), gy + 52 + MH + 20 + rr * (CH + GAP), CW, CH,
                            link_card(c, "2" if multi else "5"), "2" if multi else "5"))
            prim = (not pages.get(c, {}).get("parents")) or pages[c]["parents"][0] == mo
            edges.append({"id": nid("e"), "fromNode": mid, "fromSide": "bottom", "toNode": cid, "toSide": "top",
                          "label": "子概念" if prim else "多父", "color": "5" if prim else "2"})
            if prim:
                for other in pages.get(c, {}).get("parents", [])[1:]:
                    cross.append((cid, other))
        mid_of[mo] = mid
    for cid, other in cross:
        if other in mid_of:
            edges.append({"id": nid("e"), "fromNode": cid, "fromSide": "right", "toNode": mid_of[other], "toSide": "left",
                          "label": "多父", "color": "2"})
    return {"nodes": nodes, "edges": edges}, gfp


def _vault_rel_checked(rel):
    """把画布里的 `file` 值规范成**库根相对路径**（工作区嵌套在库根下时要带上级目录名）。"""
    pref = vault_prefix()
    s = str(rel).replace("\\", "/").lstrip("/")
    if pref and s.startswith(pref):
        return s
    try:
        return vault_rel(Path(str(rel)))
    except ValueError:
        print("[gen_canvas] 警告：%s 不在工作区内，无法计算库根相对路径" % rel, file=sys.stderr)
        return rel


def normalize_files(doc):
    """兜底：画布里所有 `file` 字段都必须是库根相对路径。

    卡片一律是 text 节点，正常不会出现 `file`；这里只是防止将来手写 file 节点时漏掉前缀。
    """
    for node in doc.get("nodes", []):
        if isinstance(node.get("file"), str) and node["file"]:
            node["file"] = _vault_rel_checked(node["file"])
    return doc


def write_canvas(path, doc):
    """写画布：UTF-8、无 BOM、LF、ensure_ascii=False（中文可读、diff 稳定）。"""
    path.parent.mkdir(parents=True, exist_ok=True)  # 空库首次生成时 wiki/ 可能还不存在
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(normalize_files(doc), f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None):
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if any(a in ("-h", "--help") for a in args):
        print(__doc__.strip())
        return 0
    unknown = [a for a in args if a != "--check"]
    if unknown:
        print("未知参数：%s\n" % " ".join(unknown), file=sys.stderr)
        print(__doc__.strip(), file=sys.stderr)
        return 2
    check_only = "--check" in args

    pages = load_pages()
    mothers = sorted(k for k, v in pages.items() if v["mother"])
    papers = {fn[:-3]: set(LINKS(rd(os.path.join(PAP, fn)))) for fn in md_names(PAP)}
    fps = {mo: fam_fingerprint(mo, pages) for mo in mothers}
    atlas, gfp = build_atlas(mothers, pages, fps)
    targets = [(overview_path(), atlas, gfp)]
    for mo in mothers:
        targets.append((family_path(mo), build_family(mo, pages, papers, fps[mo]), fps[mo]))

    # 第一轮只做体检：缺文件 → MISSING；指纹对不上 → STALE（附 旧→新 指纹）
    stale, missing = [], []
    for path, doc, fp in targets:
        name = path.name
        if not path.exists():
            missing.append(name)
            continue
        old = rd(path)
        m = FP_RE.search(old)
        if not m:
            stale.append((name, "无指纹"))
            continue
        if m.group(1) != fp:
            stale.append((name, "%s → %s" % (m.group(1), fp)))
            continue
        if not check_only:
            write_canvas(path, doc)
    if check_only:
        print("canvas 数量: %d ｜ 缺失 %d ｜ 过期 %d" % (len(targets), len(missing), len(stale)))
        for n in missing:
            print("  MISSING", n)
        for n, why in stale:
            print("  STALE  ", n, "(", why, ")")
        return 1 if (missing or stale) else 0

    # 生成模式：无论指纹是否新鲜都整体重写（坐标由本脚本唯一决定，避免手工漂移）
    written = 0
    for path, doc, fp in targets:
        write_canvas(path, doc)
        written += 1
    print("已生成 %d 张画布（总图指纹 %s）" % (written, gfp))
    for mo in mothers:
        print("  %s%s.canvas  指纹 %s" % (cfg("canvas", "family_prefix", default="wiki/概念地图-"), mo, fps[mo]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
