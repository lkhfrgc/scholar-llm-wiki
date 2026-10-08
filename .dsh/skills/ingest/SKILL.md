---
name: ingest
description: 将收件箱（默认 raw/research/）中的原始资料编译进 wiki/，处理完成后按文件类型分类归档到 raw/ 对应子目录。支持 `/ingest`（扫描收件箱下所有文件）或 `/ingest <路径>`（只处理指定文件）。当用户说「摄入」「导入」「收入」「把这篇加入知识库」「处理 raw/research/ 里的文件」时触发。
user-invocable: true
---

# ingest 技能

## 前置：初始化

若工作区里**还没有** `.dsh/wiki.config.json` 或根目录下**没有** `index.md`，说明骨架尚未生成，先跑一次：

```bash
python .dsh/scripts/setup_wiki.py
```

它按配置建好 `raw/` 收件箱、`wiki/` 五个子目录，以及 `index.md` / `log.md` / `TAGS.md` 骨架。**骨架没建好不要开始摄入**，否则后面每一步都缺落点。

## 路径以配置为准

`.dsh/wiki.config.json` 是本仓**唯一配置源**：技能与脚本都从它读目录名、文件名，仓库内不写死任何绝对路径，也不依赖当前工作目录。不确定目录到底叫什么，先自省：

```bash
python .dsh/scripts/wiki_env.py --paths     # 常用目录一览（wiki / raw / inbox / index / log / tags_doc / vocab）
python .dsh/scripts/wiki_env.py --json      # 完整配置 + 解析结果（含库根前缀、wiki_types、canvas）
```

> 下文出现的 `raw/research/`、`wiki/concepts/` 等**均为默认值**；若 `wiki.config.json` 改过目录名，以配置为准，拿不准先跑上面的自省命令。

**解释器约定**：下文用 `<venv-python>` 表示项目虚拟环境里的解释器——

- Windows：`.dsh\venv\Scripts\python.exe`
- macOS / Linux：`.dsh/venv/bin/python`

只需要标准库的步骤直接写 `python`（harness 自带的解释器即可）。**不要往系统 Python 里装包**；需要第三方依赖时一律装进项目 venv。

## 核心工作流：收件箱与归档

你正在维护一个 LLM Wiki 知识库（Obsidian 格式）。

- 收件箱（默认 `raw/research/`）是**唯一入口**——用户把所有待摄入的资料放入此处。
- `raw/` 下其他子目录是**分类归档区**——摄入完成后按类型存入。
- `wiki/` 是**编译输出层**——你负责创建和维护 wiki 子目录中的内容页面。
- `index.md` 和 `log.md` 位于工作区根目录——它们是全局注册表和操作日志。

**目录结构约定（默认值，与 AGENTS.md 一致）：**
```
raw/
├── research/        # 待处理收件箱（唯一入口，用户在此放入资料）
├── papers/          # 论文 PDF/markdown（摄入后归档至此）
├── book/            # 书籍（摄入后归档至此）⚠️ 默认目录名是单数 book
├── courses/         # 课件、课程笔记（摄入后归档至此）
├── clips/           # 网页剪藏（摄入后归档至此）
├── articles/        # 网页长文/博客（摄入后归档至此）
└── assets/          # 图片附件（摄入后归档至此）

wiki/
├── papers/          # 论文讲解页面（一篇论文一个文件）
├── concepts/        # 概念页面（一个概念一个文件）
├── connections/     # 跨概念连接（idea 产生的地方）
├── questions/       # 开放研究问题（未来方向的种子）
└── syntheses/       # 综合论述

注：`index.md` 和 `log.md` 位于工作区根目录，不在 wiki/ 下。
```

## 触发逻辑

1. **用户执行 `/ingest`**：扫描收件箱（默认 `raw/research/`），列出所有待处理文件，请用户确认后逐一处理。
2. **用户执行 `/ingest <path>`**：仅处理指定文件。
3. **隐式触发**：用户说"把这个资料摄入知识库"、"导入这篇文章"、"收入这篇论文"时，自动执行 ingest。

## 编译流水线

对每个待处理源文件，严格按以下步骤执行：

### 步骤 1：读取源文件

- **`.md` 文件**：必须完整读取。
- **`.pdf` 文件**：按「**源 → 文本 → 视觉**」三步走，**禁止一上来就整页渲染**。

  **① 源判定（最快、公式零损失，优先做）**：先看 PDF 首页有没有 arXiv ID / DOI：

  ```bash
  <venv-python> .dsh/scripts/fetch_source.py --from-pdf "<pdf_path>" -o ".dsh/tmp/_ingest_source.md"
  ```

  - 成功 → 得到「公式表（LaTeX，来自 MathML alttext）」，**公式一律以此为准**，③ 可跳过；正文仍走 ②。
  - 已知编号时用 harness 自带解释器即可（只需标准库）：`python .dsh/scripts/fetch_source.py --arxiv <编号>` 或 `python .dsh/scripts/fetch_source.py --doi <DOI>`。
  - 失败或无编号 → 继续 ②，并在 ③ 补公式。

  **② 文本路径（抽正文 + 定位公式块）**：

  ```bash
  <venv-python> .dsh/scripts/extract_pdf.py "<pdf_path>" --math --equations-json ".dsh/tmp/_ingest_eq.json" -o ".dsh/tmp/_ingest_pdf_output.txt"
  ```

  - `--math` 用字号/基线重建上下标（得到 `P_s(x)^{(i)}` 而不是 `Ps(x)(i)`），并在文首报告「公式块数 / 公式不可靠页」。
  - ⚠️ **公式不可靠页 = 数学字体缺 ToUnicode**（LaTeX 的 CMEX/CMMI/CMSY 常见）：行间 Σ 会被解成 `P`/`X` 之类，**文本路径永远修不好**。这些页的公式必须来自 ① 或 ③，**不得直接把 ② 的结果写进 wiki**。
  - 正文以 `.dsh/tmp/_ingest_pdf_output.txt` 为准。

- **③ 公式核对（只在需要时，且只渲染公式、不整页）**：当 ② 报了「公式不可靠页」，或该页公式是核心内容（损失函数、指标定义）而 ① 又拿不到源时：

  ```bash
  # 1) 用官方 LibreOffice Kit 渲染该页
  "<node>" "<libreofficeKit.cli>" render --input "<pdf_path>" --output-dir ".dsh/tmp/_ingest_render" --pages 3 --dpi 200

  # 2) 按 bbox 裁成公式小图（只用 Pillow，走 harness 自带解释器，不需要 venv）
  python .dsh/scripts/crop_equations.py --manifest ".dsh/tmp/_ingest_render/manifest.json" --equations ".dsh/tmp/_ingest_eq.json" --out-dir ".dsh/tmp/_ingest_eqcrops"
  ```

  - `<node>` 与 `<libreofficeKit.cli>` 是**占位符**，实际绝对路径由**当前加载的 office-* 技能**在「Installed LibreOffice Kit」段给出；未加载时先 `skill({ name: "office-docx" })` 取出该段再填进命令——**不要自己猜路径、也不要去找系统安装的 LibreOffice**。
  - 只用 `read_image` 读裁出的小图（每张 ~5–15 KB）；**不要渲染整页**（实测整页 ≈780 KB/页，公式块只占页面 ~5% 面积）。
  - `crop_equations.py` 输出的 `equations_index.json`（默认落在 `--out-dir` 下）记有每张图的 bbox 与文本片段，便于与 ① 的公式表逐条核对。
  - **扫描版 PDF**（`is_scanned: true` 或页面提示「无文本层」）：文本路径无效，直接走 ③ 渲染读图，**不需要 OCR**。
  - **图表/表格版式**（多子图排布、表格结构）：也走 ③，渲染相应区域或整页。

  **环境与降级**：
  - ② 需要项目内虚拟环境 `.dsh/venv/`（装 PyMuPDF），**不要往系统 Python 里装包**。
  - **venv 缺失时不要放弃摄入**：①（仅标准库）与 ③（Kit 渲染 + Pillow 裁剪）都不依赖 venv，仍能完成；缺的只是正文文本抽取。修复命令（按平台选一行）：
    ```bash
    python -m venv .dsh/venv
    # Windows:     .dsh\venv\Scripts\python.exe -m pip install -r .dsh/requirements.txt
    # macOS/Linux: .dsh/venv/bin/python -m pip install -r .dsh/requirements.txt
    ```
    并把缺失情况明确报告给用户（**不要静默跳过或改用别的解释器**）。
  - ⚠️ **不要写 `/tmp/` 之类系统临时目录**：它跨平台解析结果不一致（在 Windows 上会落到当前盘根目录）；中间产物一律写进工作区内的 `.dsh/tmp/`。
  - 脚本能力：`extract_pdf.py` 支持 `--json` / `--pages 1-5` / `--meta-only` / `--math` / `--equations-json`，自动多栏重排、识别 `is_scanned`；`fetch_source.py` 支持 `--filter display|all` / `--max-formulas` / `--json`。
  - **改动本流程或相关脚本后**，跑一遍自检：
    ```bash
    python .dsh/scripts/selfcheck.py                    # 环境与依赖自检
    python .dsh/scripts/selfcheck.py --pdf <某篇 PDF>   # 追加 PDF 流水线回归
    ```
- **其他格式**：必须完整读取。若无法提取或内容为空，改为记录文件元信息（文件名、页数）在 paper 页面中。

⚠️ **绝对禁止修改 raw/ 下任何文件的内容。**

### 步骤 2：提炼核心内容

从源文件中提取：
- **核心主旨**：这份资料讲什么（精炼的一段话）
- **关键概念**：框架、方法论、理论、算法等抽象概念
- **关键实体**：人物、机构、工具、数据集等具体名词
- **与其他已知概念的可能关联**：这份资料和已有 wiki 中的哪些概念可能产生连接

如果是非中文内容，将其翻译为简体中文（专有名词可保留英文）。

### 步骤 3：创建论文详细讲解页面

在 `wiki/papers/` 创建 Markdown 文件，**按照论文讲解模板，详细思考与讲解文献内容：**

```markdown
---
title: "论文标题"
type: paper
authors: [作者1, 作者2]
year: YYYY
venue: NeurIPS/ICML/ICLR/arXiv/期刊名等
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: ["raw/子目录/文件名"]
questions: []      # 见步骤 6
tags: []   # ⚠️ 只能从 .dsh/tag-vocab.json 的 canonical 取「分面/叶节点」，3–8 个，禁止自造词
---

## 我的批注
[留空白，以供用户进行自己的批注]

## 核心贡献
[精炼的一段话：该论文面向什么任务？该论文的核心主张、贡献或结果是什么？创新点有哪些？]

## 方法
[使用让用户容易看明白的方法讲解，必须包含：1.模型整体架构与设计思路；2.详解模型每一个模块的具体实现与原理；3.所有的数学公式都要详细讲解，公式中的每一个变量的含义都要注明。]

### 0. 全局视图

一句话概括论文任务：……

整个流水线：
[```
模型数据流
```]


**下标命名约定**：
[例如：
- $k$：
- $p$：
- $j$：
- $\ell$：
- $i$：
- ……
]


---

### 1. 模块一：[模块名称缩写及简介]（公式 1–[x]）

模块名称解释：[模块名称缩写对应的全称介绍] 模块作用：[讲解该模块的作用和意义]。

#### 公式 (1)：[公式简介，讲解该公式的作用和意义]

$$公式$$

| 符号       | 含义                                    | 形状                         |
| -------- | ------------------------------------- | -------------------------- |
| $公式符号$   | [符号含义]                                | $公式符号形状$                   |

**人话**：[用通俗易懂、易于理解的方式向用户讲解公式]
> ([可选：补充说明])

## 关键结果
[有什么进步？做了哪些实验？展示了什么？尽量量化。]

## 局限性与开放问题
[它的局限性是什么？做了哪些假设？有什么改进方向？]
[必须跟据原文内容提出三个关键问题，并给予简要的解答。]

### 问题与解答
**Q1: 问题1**
> 解答：

**Q2: 问题2**
> 解答：

**Q3: 问题3**
> 解答：
……

### 局限性分析

**局限性1**
> 分析：

**局限性2**
> 分析：
……

## 关联连接
- [[概念-1]]：该论文与之的关系
- [[概念-2]]：该论文与之的关系

## 原始来源
- [[raw/子目录/文件名]]
```

**命名规则**：`<来源年份>-<简短标题>.md`（例：`NeurIPS2024-<方法缩写>.md`、`2023-<标题关键词>.md`；年份取来源发表年份，标题取能一眼认出的短名）。

### 步骤 4：知识网络化 — 概念页面

对于步骤 2 提取的每个关键概念，在 `wiki/concepts/` 中处理：

**若概念页面不存在** → 按概念页面模板创建：

```markdown
---
title: "概念名称"
type: concept
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: ["raw/子目录/文件名"]
questions: []      # 见步骤 6
tags: []   # ⚠️ 只能从 .dsh/tag-vocab.json 的 canonical 取「分面/叶节点」，3–8 个，禁止自造词
代码仓库: []   # 代码仓库链接
---

## 定义
[这个概念是什么？请精确表述。]

## 核心思想
[核心机制、方程、直觉。]

## 关联连接
- [[相关概念]]：关系
- [[相关论文]]：贡献

## 开放问题
[关于这个概念还有什么未解决的？]
```

**若相近的概念页面已存在**：
1. 读取现有内容
2. **增量合并**新信息（在 `sources` 中添加新来源，在对应章节中补充新内容）
3. **若发现新旧知识冲突** → 立即暂停，进入[冲突处理流程](#冲突处理流程)

**命名规则**：使用中文命名，简洁准确反映概念核心含义（如 `稀疏编码.md`、`对比学习.md`）。专有名词/缩写（如 LoRA、Mamba、Stem、SSM）可保留英文。

### ⚠️ 步骤 4b：链接前必须消歧（死链的主要来源）

写任何 `[[概念名]]` 之前，**先确认目标页面到底叫什么**——不要凭英文 slug 或记忆直接写链接。判断顺序：

1. 先 `glob` 或 `grep` 查 `wiki/concepts/` 是否已有同名或近义页面
2. 若已存在页面：**逐字使用它的文件名**（不带 `.md`）作为链接目标
3. 若不存在页面：按上面规则新建，再链接

**为什么必须这么做**：同一概念曾被同时写成英文 slug（`[[sparse-coding-attention]]`）和中文文件名（`稀疏编码与注意力.md`）两种形式，一轮巡检就暴露出多处死链（同一目标被多个页面引用、却始终没有对应文件）。根因不是粗心，而是**没有先查后写**。

**硬性要求**：新页面一旦建立，**链接目标必须与文件名逐字一致**。若想保留英文别名，用 Obsidian 别名语法 `[[中文文件名|English Alias]]`，**不要**把链接目标写成英文 slug。

### 步骤 5：创建跨概念连接

检查此资料是否在已有概念之间建立了**新的连接**。满足以下任一条件即视为新连接：

- 两个已有概念在此资料中首次被一起讨论
- 此资料揭示了一个概念对另一个概念的影响或依赖关系
- 此资料提供了连接两个概念的桥梁机制

若存在新连接，按照模版在 `wiki/connections/` 创建连接页面：

```markdown
---
title: "连接简述"
type: connection
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: ["raw/子目录/文件名"]
tags: []   # ⚠️ 只能从 .dsh/tag-vocab.json 的 canonical 取「分面/叶节点」，3–8 个，禁止自造词
---

## 涉及概念
- [[概念A]]
- [[概念B]]

## 连接本质
[这两个概念之间是什么关系？类比、依赖、对立、统一框架？]

## 证据
[来源中支持此连接的具体内容。]

## 启示
[这个连接带来了什么新的理解或研究方向？]

## 关联连接
- [[概念A]]：连接的一端
- [[概念B]]：连接的另一端
- [[相关论文]]：该连接的证据来源
```

⚠️ **`## 关联连接` 是必需小节，不能省**：AGENTS.md 规定「每一个 wiki 页面必须包含 `## 关联连接` 区域……绝不能产生孤岛页面」。**经验**：只靠 `## 涉及概念` 结尾是最常见的漏法——这类页面在 `## 涉及概念` 里列了链接，却没有任何页面反向引用它，实际成了半个孤岛。

**命名规则**：使用中文命名，格式为 `连接-主题.md`（如 `连接-稀疏编码与注意力.md`、`连接-自监督预训练与对比学习.md`）。文件名应简洁概括连接的本质关系。

### 步骤 6：标注核心研究问题

查阅 `wiki/` 下是否有定义核心研究问题的文件。如果有，判断此资料回答了哪些核心问题，并在 paper 页面和 concept 页面的 frontmatter `questions` 字段中标注对应编号。

如果此资料提出了**全新的研究问题**，在 `wiki/questions/` 创建问题页面：

```markdown
---
title: "问题简述"
type: question
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: ["raw/子目录/文件名"]
questions: []      # 该问题自身关联的核心问题编号
tags: []   # ⚠️ 只能从 .dsh/tag-vocab.json 的 canonical 取「分面/叶节点」，3–8 个，禁止自造词
---

## 问题陈述
[精确表述这个开放问题。]

## 动机
[为什么这个问题重要？]

## 相关概念
- [[概念-1]]
- [[概念-2]]

## 可能路径
[目前有哪些可能的解决思路？]

## 关联连接
- [[概念-1]]：与该问题的关系
- [[相关论文]]：已有的部分回答
```

⚠️ **question 页面同样需要 `updated`、`sources` 和 `## 关联连接`**。**经验**：只写 `title/type/created/tags` 四个字段的 question 页面最容易漏掉这三个——模板里少写一个字段，后面就会成批地漏。

**命名规则**：`q-简短描述.md`

### 步骤 6b：为本次所有页面选取 tag（受控词表，硬性）

**这一步不是可选的**——tag 是封闭词表，写错会让 `tag_audit.py` 报错。

1. **列出当前词表**：`python .dsh/scripts/tag_vocab.py --list`，或直接读 `.dsh/tag-vocab.json` 的 `canonical`。
   注意 `TAGS.md` 是**规则**文档、**不列词条**，别去那里找词。
   从中**挑**而不是**造**。每个主题 tag 形如 `分面/叶节点`，分面只有七个：
   `domain` / `task` / `modality` / `method` / `challenge` / `data` / `meta`。
2. 每页选 **3–8 个**（推荐 3–5），逐分面问一遍：
   这页服务于哪个平台/领域？输出是什么？输入什么模态？用了什么机制？是什么让任务变难？
   涉及哪个数据集/基准？是综述还是实验分析？——答得上就挂，答不上就不挂。
3. **复合概念拆开**：不要写 `xxx-detection` 这类复合 tag，要写成 `modality/<模态>` + `task/detection`。
4. **不要**用 tag 表达 `type`、年份、数据集专名、模型专名——已有 `type`/`year` 字段，
   数据集专名归 `data/dataset`，模型专名归 `method/foundation-model`。
5. **角色 tag 例外**：若本页是母页/子页，`母概念` / `子概念` 仍按 AGENTS.md 放在
   `tags` **第一位**（它们不带分面前缀）。
6. 写成**单行内联**：`tags: [task/detection, modality/<模态>, method/<机制>]`；
   母页/子页把角色 tag 写在最前。顺序 = 角色 tag → domain → task → modality → method → challenge → data → meta → 面内字母序。
7. 若确实需要一个词表里没有的 tag：先确认它**在 ≥3 个页面上有检索价值**且能归入某个分面；
   通过则按下表五步登记到词表，再使用。**不通过就换成最接近的现有词条，或干脆不挂。**

**词表改动流程（五步，缺一不可）**：

1. 在 `.dsh/tag-vocab.json` 的 `canonical` 加 `叶节点: 中文释义`，在 `map` 里登记来源词；
2. `python .dsh/scripts/tag_vocab.py --check` —— 词表自洽；
3. （仅当改了**分面或规则**）`python .dsh/scripts/tag_vocab.py --emit-doc` —— 重新生成 `TAGS.md`；
4. `python .dsh/scripts/tag_apply.py`（预演）→ `--apply`（写盘，自动备份到 `.dsh/tmp/tags-backup-*.json`）；
5. `python .dsh/scripts/tag_audit.py` —— 复核，退出码必须为 0。

**收尾自检**（必须做）：

```bash
python .dsh/scripts/tag_audit.py          # 退出码必须为 0
```

### 步骤 7：更新全局注册表

**更新 `index.md`：**
将本次新增或修改的页面按分类加入目录，每一条都在所属类别的小节的顶部。格式：
```markdown
## Papers
- [[PaperPage]] — 一句话描述核心贡献

## Concepts
- [[ConceptName]] — 一句话定义

## Connections
- [[conn-topic]] — 一句话描述连接本质

## Questions
- [[q-topic]] — 一句话描述开放问题

## Syntheses
- [[synthesis-slug]] — 一句话说明它回答的复杂问题
```

> 段名固定为这五段（与 AGENTS.md「内容分类」、lint 检查 1 一致），不要自造段落。

**更新 `log.md`（将操作记录追加到文件顶部，不可覆盖已有内容）：**

⚠️ **写入前检查格式**：操作类型只允许 `ingest / query / lint`。**经验**：不加约束时日志会长出 `enrich`、`synthesize`、`delete` 之类的规范外类型；新条目必须**独占一行**并以空行结尾——两条记录粘连在同一行的排版事故出现过。追加后回读一眼，确认新条目的开头是 `## [` 而不是接在旧内容后面。

```markdown
## [YYYY-MM-DD] ingest | 资料标题
- **变更**: 新增 [[PageA]], [[PageB]]; 更新 [[ExistingPage]]; 更新 [[index.md]]
- **冲突**: 无
```
或：
```markdown
## [YYYY-MM-DD] ingest | 资料标题
- **变更**: 新增 [[PageA]]; 更新 [[index.md]]
- **冲突**: 冲突 [[ConflictingPage]]，已标注知识冲突区块
```

### 步骤 8：分类归档源文件

确认以下全部完成后，将源文件从收件箱 **移动**到 `raw/` 下对应的分类子目录：

- [ ] paper 页面已创建
- [ ] concept 页面已创建或更新
- [ ] connection 页面已创建（如有）
- [ ] 核心研究问题已标注
- [ ] `index.md` 已更新
- [ ] `log.md` 已追加

**分类规则**（根据文件内容判断，而非仅看文件名）：

| 资料类型 | 目标目录（默认值） |
|---|---|
| 学术论文（期刊/会议/预印本） | `raw/papers/` |
| 书籍或书章节 | `raw/book/` ⚠️ 默认是单数 |
| 课程讲义、课件、教程 | `raw/courses/` |
| 网页剪藏、博客文章 | `raw/articles/`（长文/博客）或 `raw/clips/`（短剪藏） |
| 图片、图表、示意图 | `raw/assets/` |

⚠️ **移动前必须验证目标目录真实存在**。**经验**：规范里的目录名与磁盘上的实际目录名出现过单复数不一致（如 `raw/book/` 与 `raw/books/`）——遇到这种差异**停下来报告并询问用户**用哪个，不要自行创建新目录、也不要静默跳过归档，两者都会让收件箱越积越乱。

⚠️ **归档只是移动文件位置，绝对禁止修改源文件内部的文字。**

归档后，更新 paper 页面中 `sources` 字段的路径以反映新位置（如 `raw/research/xxx.pdf` → `raw/papers/xxx.pdf`）。

### 步骤 9：族结构变化时重生成 Canvas（强制收尾）

只要本轮 ingest **改动了概念分层**，就必须重新生成画布——否则 Obsidian 里的族地图会展示陈旧结构（错误分组、缺失子页、指向已改名页面的链接）。触发条件（满足任一）：

- 新增/删除母页，或新增/删除母页 `## 子概念` 段里的子页条目
- 修改母页 `## 子概念` 段的分组标题（分组框会变）
- 修改子页文首的 `> **母概念**：…` 定位行（多父关系变化）
- 母页改名

执行：

```bash
python .dsh/scripts/gen_canvas.py           # 重新生成总图 + 各族的 wiki/概念地图-<族>.canvas
python .dsh/scripts/gen_canvas.py --check    # 校验：退出码 0 = 全部新鲜；非 0 会列出 MISSING / STALE
```

（画布文件名以 `wiki.config.json` 的 `canvas` 段为准；总图与族图前缀见配置。）

报告时必须写明：**哪几张画布被重新生成 / 是否有 STALE**（只报受影响的族图 + 总图，其余族图不受影响）。若本轮未触及分层结构，写一句"未触及族结构，无需重生成"即可。

## 冲突处理流程

当新旧知识冲突时：

1. **暂停**：停止当前 ingest 流程
2. **报告**：向用户清晰说明：
   - 哪个页面存在冲突
   - 旧说法是什么（引用来源）
   - 新说法是什么（引用当前资料）
   - 冲突的本质是什么
3. **询问**：请用户选择处理方式：
   - **A) 并存标注** — 在页面中新建 `## 知识冲突` 区块，保留新旧两种说法并做对比。推荐用于学术争议。
   - **B) 新覆盖旧** — 用新知识替换旧知识。适用于新资料更正了旧错误的情况。
   - **C) 保留旧说** — 放弃本次对此概念的更新。适用于新资料来源不够可靠时。
   - **D) 跳过此概念** — 本次不处理此概念，其余继续。
4. **继续**：根据用户选择执行，并在 `log.md` 中记录冲突处理结果。

## 注意事项

- 只处理收件箱（默认 `raw/research/`）下的文件。`raw/` 其他子目录中的文件是已归档资料，除非用户明确指定，否则不重新处理
- 所有 wiki 页面必须包含 `## 关联连接` 区域，不能产生孤岛页面
- 使用简体中文编写所有内容，专有名词可保留英文
- 面向具有扎实数学/计算机背景的读者，不要降格简化
- 中英文混用没问题 — 用对概念最清晰的表达方式
- 每次 ingest 结束后，主动向用户汇报：新增了哪些页面、更新了哪些页面、有无冲突

---

## 关联连接

- [[index]] — 全局索引入口
- [[log]] — 操作日志
- [[AGENTS.md]] — Wiki 架构总规范
