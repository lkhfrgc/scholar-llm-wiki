# 架构

## 1. 三层结构

```
raw/        不可变层   人的事实来源；只读、只归档，永不改内容
  ↓  编译（ingest 技能）
wiki/       编译输出层 AI 的专属工作区；五类页面，一页一类
  ↓  注册（每次写入的收尾动作）
index.md    总目录      五个固定段落
log.md      操作日志    只追加，只允许 ingest / query / lint
```

**为什么这么分**：事实来源与加工产物必须物理隔离。一旦允许 agent「顺便优化」原文，
知识库就再也无法回溯「这句话当初是从哪来的」。归档 = 移动文件位置，不是修改内容。

## 2. 五类页面

| 目录 | `type` | 收录判据 |
|---|---|---|
| `wiki/papers/` | `paper` | 一篇论文一页：核心贡献 / 方法拆解（`### 0. 全局视图` + 模块化公式讲解）/ 实验 / 局限 |
| `wiki/concepts/` | `concept` | 一个概念一页：定义 / 数学形式 / 与上下游的关系 |
| `wiki/connections/` | `connection` | 两概念之间 **relates-to** 的连接、类比、张力 |
| `wiki/questions/` | `question` | 开放研究问题：现状 / 为何未解 / 切入路径 |
| `wiki/syntheses/` | `synthesis` | 跨多页的复杂问题的综合论述 |

分类由**「页面回答什么」**决定，不由来源决定：同一篇论文可以同时产出 paper + concept +
connection 三页，各进各的目录，再用 `[[双链]]` 互相连接。

## 3. ingest 的数据流

```
raw/research/ 的源文件
   │
   ├─ .md          → 完整读取
   ├─ .pdf         → ① fetch_source.py 取 arXiv/DOI 的 LaTeX 公式真值（仅标准库）
   │                 ② extract_pdf.py 抽正文 + 定位公式块 bbox（需 PyMuPDF）
   │                 ③ crop_equations.py 按 bbox 裁公式小图（需 Pillow；扫描版必走）
   └─ 其它格式      → 完整读取，读不动就只记元信息
   │
   ├─→ wiki/papers/<来源年份>-<短标题>.md      论文讲解页
   ├─→ wiki/concepts/*.md                      概念页（新建或增量合并）
   ├─→ wiki/connections/连接-*.md              新连接（如有）
   ├─→ wiki/questions/q-*.md                   新研究问题（如有）
   │
   ├─→ 步骤 6b：从 .dsh/tag-vocab.json 挑 tag（封闭词表，禁止造词）
   ├─→ 步骤 7：更新 index.md（五段，新条目插顶部）+ log.md（顶部追加）
   ├─→ 步骤 8：把源文件从 raw/research/ 移到 raw/<类别>/
   └─→ 步骤 9：族结构若变化 → gen_canvas.py 重生成画布
```

**三个"硬收尾"**：更新 `index.md`、追加 `log.md`、重生成 Canvas。
不做就等于没做完 —— 它们是写入流程的一部分，不是可选礼貌。

## 4. 脚本地图

### 环境层（所有脚本的地基）

| 脚本 | 职责 |
|---|---|
| `wiki_env.py` | **全仓唯一允许"找路径"的地方**。从自身位置上溯两级推出工作区根；向上找 `.obsidian/` 算出库根前缀；深合并 `.dsh/wiki.config.json` 与内置默认值；跨平台解析解释器。其余脚本一律 `from wiki_env import ...` |

### 入口层

| 脚本 | 职责 | 退出码 |
|---|---|---|
| `setup_wiki.py` | 建目录骨架（目录名从 `wiki_types` 的键来）+ 生成 `index.md`/`log.md`/`TAGS.md`；**幂等，绝不覆盖** | 非 0 = 有步骤失败 |
| `selfcheck.py` | 体检：工作区/配置/骨架/解释器/可选依赖/子脚本自检；`--pdf` 追加 PDF 流水线回归 | 非 0 = 必需项失败 |

### tag 子系统

```
.dsh/tag-vocab.json          ← 词表数据（facets / canonical / map / page_overrides）
        │
tag_vocab.py                 ← 引擎：加载数据 → CANONICAL / MAP / ORDER / translate / check / emit_doc
        ├─ --check            ←  自洽性：map 指向的词条存在、无死词条、分面合法
        ├─ --emit-doc         ←  生成 TAGS.md（人读文档）
        ↓
tag_apply.py                 ← 按 map 批量改写页面 frontmatter 的 tags 行（预演 / --apply / --rollback）
tag_audit.py                 ← 全库审计：未登记 tag、超限、频次分布
tag_verify_migration.py      ← 独立复核：备份 → 重新推导 → 与磁盘逐页比对
```

三条设计约束：

- **词表是数据不是代码** —— 只有放在 JSON 里才能被审计、被 diff、被迁移；
- **改写只动 `tags:` 一行** —— 走 `read_bytes`/`write_bytes`，连行尾符都不归一化，git diff 干净；
- **映射是幂等的** —— 对已是规范 tag 的页面重复执行不产生变化。

### 概念分层与画布

```
wiki/concepts/*.md
   ├─ 母页：tags 首项 = 母概念，正文有 `## 子概念` 段（bullet 决定分组）
   └─ 子页：tags 首项 = 子概念，文首有 `> **母概念**：[[母页]]` 定位行（决定多父）

gen_canvas.py
   ├─ 结构指纹 = hash(母页名 + 子页集合 + 各子页父页列表)[:8]
   ├─ 总图  wiki/概念全景图.canvas
   ├─ 族图  wiki/概念地图-<母页名>.canvas
   └─ --check  比对画布内记录的指纹与当前 wiki 结构 → MISSING / STALE
```

**画布卡片一律 `text` 节点 + `[[双链]]`，禁止 `file` 节点** —— 后者会把笔记正文
嵌入画布渲染，卡片一多开销爆炸。画布内的 `file` 字段必须带库根前缀，否则
Obsidian 显示「未找到引用的文件」。

### 校验器

| 脚本 | 职责 |
|---|---|
| `check_paper_template.py` | 论文页 8 项模板判定；`--links` 做全库死链检查（按 basename 全局唯一解析，排除文档占位符 / 历史日志 / 路径型引用三类假死链）。扫描源是 `wiki/**` + 根 `index.md` —— `log.md` 是历史记录、说明性文档里的链接是格式示例，都不参与判定；要覆盖 `AGENTS.md` 里的链接，用 lint 技能的检查 2 |

> 注意：`--links` 是给 CI 用的**子集**检查；lint 技能跑的是完整版（含根目录文档、
> 孤儿页分级、命名不一致归类）。两者不冲突，但结论范围不同。

### PDF 三件套

| 脚本 | 依赖 | 为什么需要它 |
|---|---|---|
| `fetch_source.py` | 仅标准库 | arXiv 的 HTML 版里每个 `<math>` 都带 `alttext`，那就是**逐字准确的 LaTeX 源码**，比任何 OCR 都可靠 |
| `extract_pdf.py` | PyMuPDF | 抽全文、多栏重排；`--math` 用字号/基线重建上下标；报告「公式不可靠页」 |
| `crop_equations.py` | Pillow | 只渲染公式区域（约占页面 5% 面积）而不是整页（≈780 KB/页），省几十倍 token |

**「公式不可靠页」为什么要单独报**：LaTeX 数学字体常常没有 ToUnicode 表，
行间 Σ 会被文本层解成 `P`/`X`。这类页面**文本路径永远修不好**，公式必须来自
① 的 LaTeX 源，或 ③ 的渲染读图 —— 不得把文本层结果直接写进 wiki。

## 5. 技能层

技能是 Markdown，靠 frontmatter 的 `description` 被 harness 自动选中。

| 技能 | 流水线 |
|---|---|
| `ingest` | 9 步：读源 → 提炼 → 论文页 → 概念页 → 消歧链接 → 连接页 → 问题标注 → tag → 注册表 → 归档 → Canvas |
| `query` | 5 步：读 `index.md` 定位 → 深读 2–5 页 → 带双链综合 → 新洞见固化 → 记日志 |
| `lint` | 9 项检查（索引一致性 / 死链孤儿 / 缺失概念 / 过时论断 / 问题覆盖 / 空白领域 / 分层一致性 / Canvas 同步 / Tag 合规），**默认只读** |

三个技能共享同一份 `AGENTS.md` 契约，所以产出物结构长期稳定 —— 这是
「AI 维护的知识库」和「一堆 AI 生成的散页」的区别所在。

## 6. 配置的边界

`.dsh/wiki.config.json` 只描述**相对结构**，不含任何绝对路径：

```json
{
  "vault_prefix": "auto",
  "dirs":     { "wiki": "wiki", "raw": "raw", "inbox": "raw/research", "archive": {…} },
  "files":    { "index": "index.md", "log": "log.md", "tags_doc": "TAGS.md", "vocab": ".dsh/tag-vocab.json" },
  "wiki_types": { "papers": "paper", "concepts": "concept", … },
  "canvas":   { "overview": "wiki/概念全景图.canvas", "family_prefix": "wiki/概念地图-" },
  "python":   { "venv": ".dsh/venv", "requirements": ".dsh/requirements.txt" }
}
```

绝对位置由 `wiki_env.py` 在运行时推导。这一条是「一份仓库装到任何机器都能跑」的全部秘密：
**配置里没有机器信息，所以配置可以随便提交。**

## 7. 扩展点

| 想加什么 | 加在哪 |
|---|---|
| 新技能 | `.dsh/skills/<name>/SKILL.md` + `AGENTS.md` 的调度表 |
| 新的审计维度 | 仿 `tag_audit.py`：只读、`--json`、退出码说话 |
| 新的目录分区 | `wiki.config.json` 的 `dirs` + `wiki_types` |
| 新领域词表 | `tag-vocab.json` 的 `canonical` + `map`，然后 `--check` |
| CI 校验 | 直接串：`tag_vocab.py --check && tag_audit.py && gen_canvas.py --check && check_paper_template.py` |
