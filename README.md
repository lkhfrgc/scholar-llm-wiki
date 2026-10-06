# ScholarWiki Kit

> **文献进，知识出。** 面向**科研与文献整理**的知识库工具包：AI agent 把论文、书籍、课件、网页长文**编译**成结构化、高度互链的 Obsidian 知识库。
>
> ***Sources in, knowledge out.** A knowledge base toolkit for research and literature review. AI agents compile papers, books, course notes and articles into a structured, densely interlinked Obsidian wiki — not a one-off summary, but a persistent artifact that compounds with every source you add. Built on Andrej Karpathy's [llm-wiki.md](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern, plus a controlled tag vocabulary, concept hierarchy with generated Canvas maps, an arXiv→LaTeX formula pipeline, and audits that speak through exit codes. Zero hardcoding. Docs are in Chinese.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-%E2%89%A53.9-blue.svg)
![Dependencies](https://img.shields.io/badge/deps-stdlib%20only%20(optional%3A%20PyMuPDF%2C%20Pillow)-green.svg)
![Best with Obsidian](https://img.shields.io/badge/best%20with-Obsidian-7C3AED.svg)
![Skill host: DSH](https://img.shields.io/badge/skill%20host-DSH-4B8BBE.svg)
![For research](https://img.shields.io/badge/for-%E7%A7%91%E7%A0%94%E4%B8%8E%E6%96%87%E7%8C%AE%E6%95%B4%E7%90%86-2E7D32.svg)

> 📖 **新手请直接看 [用户手册 `docs/MANUAL.md`](docs/MANUAL.md)** —— 从「这东西是干什么的」讲到「出问题怎么修」。
>
> 🧠 **方法论出处**：本工具包的基础方法论来自 **Andrej Karpathy 的 [`llm-wiki.md`](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**——
> 「让 LLM 增量维护一个持久 wiki」这个想法是他的；本仓库做的是把它工程化、脚本化、做成可安装的工具。详见[下文](#方法论出处)。

它不是「笔记模板」，而是一套**可执行的知识库契约**：

- `AGENTS.md` —— 给 AI 的架构规范：目录权限边界、页面分类、命名规则、双链、tag 受控词表、概念分层、Canvas 同步；
- 三个技能（`ingest` / `query` / `lint`）—— 把「摄入资料 → 生成页面 → 维护索引 → 健康巡检」固化成流水线；
- 一沓脚本 —— 路径自省、骨架初始化、tag 审计、概念地图生成、PDF 公式提取、环境自检；
- 一份配置 —— 所有目录名、领域、词表都在 JSON 里，**仓库内零硬编码、零绝对路径**。

---

## 它面向什么：科研与文献整理

**这不是通用笔记应用**——没有待办、日记、看板、周计划。它是**文献进、知识出**的编译器，
按「一位研究者在几个月里持续读论文」这个场景设计的。具体对应关系：

| 科研中的真实痛点 | 工具包给的解法 |
|---|---|
| 论文读完就忘，重读又要从头开始 | **论文讲解页**：不是摘要，而是「核心贡献 → 模块化拆解 → 每个公式配符号表 + 人话解读 → 实验与局限」。结构由 `check_paper_template.py` 强制校验 |
| 概念散落在几十篇文献里，形不成体系 | **概念页 + 两级分层**：一个概念一页；统领 ≥3 页的升为母页，在 Obsidian 关系图谱里能直接看见骨架 |
| 「这个想法我好像在哪篇见过」 | **双链 + 关系图谱**；`/query` 必须先读你的库再回答，**禁止凭模型记忆**，答案带 `[[双链]]` 引用 |
| 没时间维护目录、交叉引用、改名后的链接 | `/ingest` 的收尾动作**强制**更新 `index.md`、追加 `log.md`、重生成概念地图；`/lint` 定期抓死链与孤儿页 |
| 新读的文献和旧结论矛盾，不知道以哪个为准 | **`## 知识冲突` 区块**显式并存两种说法；lint 的「过时论断」检查会标出可能被新资料推翻的页面 |
| 研究问题追着追着就散了 | `wiki/questions/` 专门存开放问题，frontmatter 的 `questions` 字段把页面与问题挂起来，lint 出覆盖矩阵 |
| 公式抄错、上下标丢失、Σ 被解成 `X` | **PDF 公式流水线**：arXiv/DOI 取 LaTeX 真值 → 抽正文定位公式块 → 按 bbox 裁公式小图核对。识别「公式不可靠页」并拒绝把错误结果写进笔记 |
| 标签越打越乱，最后检索不动 | **7 分面受控词表**（领域 / 任务 / 模态 / 方法 / 问题 / 数据 / 元信息），封闭词表 + 审计脚本，防止标签膨胀 |
| 时间跨度以月计，半年后要能看懂 | 页面按「面向有扎实数学/计算机背景的读者」写，不做降格简化；`log.md` 保留完整时间线 |

> **为什么专门标注这一点**：Karpathy 的原始 pattern 是通用知识管理（也能用来记健康、
> 读小说、做竞品分析）。本仓库把它实例化成了**科研文献整理**这一个具体形状——
> 论文讲解模板、公式流水线、概念分层、受控词表，都是为这个场景加的。
> 如果你要做的是别的领域，这套代码照样能用，但可能要换掉论文模板和那套 tag 词表
> （见 [`docs/CUSTOMIZE.md`](docs/CUSTOMIZE.md)）。

---

## 运行环境（装之前先看这一段）

**最佳体验 = Obsidian + DSH（DeepSeek Harness）。** 这两者不是可选项，而是这套工具「能跑」和「好用」的分界线：

| 组件 | 角色 | 没有它会怎样 |
|---|---|---|
| **DSH（DeepSeek Harness）** | **技能宿主**。它读取 `.dsh/skills/<name>/SKILL.md`，把 `/ingest`、`/query`、`/lint` 变成可触发的流水线；同时自动加载 `AGENTS.md` 作为工作规范 | 13 个脚本照样能用（纯 Python），但三个技能不会自动触发，`AGENTS.md` 也不会自动生效——你得手动指挥每一步 |
| **Obsidian** | **呈现层**。`[[双链]]` 的反向链接、关系图谱、`.canvas` 概念地图、tag 面板都由它渲染 | 页面仍是标准 Markdown，能用任何编辑器打开；但**关系图谱、反向链接和概念地图看不到**，知识网络的「网」就退化成一堆散文件 |
| **Python ≥ 3.9** | 全部脚本的运行环境 | 脚本无法运行，只剩 `AGENTS.md` 规范文本 |
| PyMuPDF / Pillow / LibreOffice Kit | 只服务 PDF 公式提取 | PDF 正文与公式走不了自动路径，其它功能不受影响（脚本会给出安装指引） |

一句话：**DSH 负责「怎么干」，Obsidian 负责「看得见」。**

> 想换个 harness（Claude Code / Cursor 等）？脚本层完全可移植，只需把 `.dsh/skills/` 搬到该
> harness 的技能目录、把 `AGENTS.md` 复制成它认识的指令文件。技能正文引用了 DSH 的工具名
> （`skill` / `grep` / `glob` / `read` / `read_image`）与 `office-docx` 技能，换宿主时需要
> 相应替换——这一步是机械劳动，但必须做，否则技能会「找工具失败」而退化成凭记忆回答。

---

## 🚀 一句话安装

把下面这一整句发给你的 DSH，它会自己完成全部安装：

> **请安装 ScholarWiki Kit：把 `https://github.com/YOUR-NAME/scholar-wiki-kit` 克隆到临时目录（没有 git 就下载 zip 解压），将仓库里的 `.dsh/`、`AGENTS.md`、`templates/` 复制到当前工作区（`.dsh/` 按目录合并，任何已存在的同名文件都不要覆盖，冲突项另存为 `<原文件名>.kit-new`），然后依次运行 `python .dsh/scripts/setup_wiki.py` 与 `python .dsh/scripts/selfcheck.py`，把体检报告原样贴给我，并提醒我把待摄入资料放进 `raw/research/`；全程不要修改 `raw/` 下的任何文件。**

<details>
<summary>更短的版本（先试 clone，失败再手工）</summary>

> **克隆 `https://github.com/YOUR-NAME/scholar-wiki-kit`，把里面的 `.dsh/` 和 `AGENTS.md` 复制到当前工作区（不要覆盖已有文件），跑 `python .dsh/scripts/setup_wiki.py`，然后把 `selfcheck.py` 的结果给我看。**

</details>

<details>
<summary>不用 agent，手工装（30 秒）</summary>

```bash
git clone https://github.com/YOUR-NAME/scholar-wiki-kit /tmp/scholar-wiki-kit
cp -r /tmp/scholar-wiki-kit/.dsh /tmp/scholar-wiki-kit/AGENTS.md /tmp/scholar-wiki-kit/templates .   # 合并式复制
python .dsh/scripts/setup_wiki.py
python .dsh/scripts/selfcheck.py
```

Windows PowerShell：

```powershell
git clone https://github.com/YOUR-NAME/scholar-wiki-kit $env:TEMP\scholar-wiki-kit
Copy-Item $env:TEMP\scholar-wiki-kit\.dsh, $env:TEMP\scholar-wiki-kit\AGENTS.md, $env:TEMP\scholar-wiki-kit\templates . -Recurse
python .dsh/scripts/setup_wiki.py
python .dsh/scripts/selfcheck.py
```

</details>

装完以后你会得到：

```
你的知识库/
├── AGENTS.md          # AI 的架构规范（每次对话自动生效）
├── TAGS.md            # tag 受控词表（脚本生成，勿手改）
├── index.md           # 总目录
├── log.md             # 操作日志（append-only）
├── .dsh/
│   ├── wiki.config.json    # 唯一配置源
│   ├── tag-vocab.json      # 词表数据
│   ├── skills/{ingest,query,lint}/SKILL.md
│   └── scripts/*.py
├── raw/research/      # ← 把待摄入的资料丢这里
└── wiki/{papers,concepts,connections,questions,syntheses}/
```

---

## 30 秒上手

1. 把一篇论文 PDF（或 markdown、网页剪藏）丢进 `raw/research/`；
2. 对 agent 说 **`/ingest`**（或「把 raw/research 里的资料摄入知识库」）；
3. 摄入完成后到 Obsidian 里看：`wiki/papers/` 有论文讲解页，`wiki/concepts/` 有概念页，`index.md` 已更新，`log.md` 有记录，概念地图 `.canvas` 已重新生成；
4. 之后随时 `/query 某个问题` 检索，或 `/lint` 做一次全库体检。

---

## 三个技能

| 技能 | 触发 | 做什么 |
|---|---|---|
| **ingest** | `/ingest`、`/ingest <路径>`、「摄入」「导入」 | 读源文件 → 建论文讲解页（含公式符号表 +「人话」解读）→ 抽概念页 → 找跨概念连接 → 标注研究问题 → 选 tag → 更新 `index.md` / `log.md` → 归档源文件 → 重生成 Canvas。**全程禁止修改 `raw/`** |
| **query** | `/query <问题>`、「wiki 里有没有…」 | 先读 `index.md` 定位 → 深读相关页面 → 带 `[[双链]]` 引用综合回答；**禁止凭模型记忆回答**；发现新洞见主动提议固化为 synthesis / connection / question 页面 |
| **lint** | `/lint`、`/scan` | 九项检查：索引一致性、死链与孤儿页、缺失概念、过时论断、问题覆盖、空白领域、概念分层一致性、Canvas 同步、Tag 词表合规。**默认只读**，修复需确认 |

三个技能都建立在同一份 `AGENTS.md` 契约上，因此输出结构长期稳定。

---

## 工具链

```bash
python .dsh/scripts/wiki_env.py --paths        # 自省：工作区根 / 库根前缀 / 所有路径
python .dsh/scripts/setup_wiki.py              # 初始化骨架（幂等，绝不覆盖已有内容）
python .dsh/scripts/setup_wiki.py --venv       # 顺带建 venv 装 PyMuPDF
python .dsh/scripts/selfcheck.py               # 体检：环境 / 依赖 / 骨架 / 子脚本

python .dsh/scripts/tag_vocab.py --check       # 词表自洽性
python .dsh/scripts/tag_vocab.py --emit-doc    # 刷新 TAGS.md
python .dsh/scripts/tag_audit.py               # 全库 tag 审计（非 0 = 有未登记 tag）
python .dsh/scripts/tag_apply.py [--apply]     # 按 map 批量迁移历史 tag
python .dsh/scripts/tag_apply.py --rollback <备份.json>          # 精确回滚
python .dsh/scripts/tag_verify_migration.py    # 独立复核迁移结果

python .dsh/scripts/gen_canvas.py [--check]    # 生成 / 校验概念地图画布
python .dsh/scripts/check_paper_template.py    # 论文页模板合规校验（--links 顺带查死链）

python .dsh/scripts/repo_lint.py               # 提交前扫描：绝对路径 / 用户名 / 凭据 / BOM / 失效链接

python .dsh/scripts/fetch_source.py --arxiv 1706.03762v7   # arXiv/DOI → LaTeX 公式真值（仅标准库）
python .dsh/scripts/extract_pdf.py paper.pdf --math -o out.txt     # PDF 正文抽取（需 PyMuPDF）
python .dsh/scripts/crop_equations.py --manifest m.json --equations e.json --out-dir crops/  # 裁剪公式小图（需 Pillow）
```

审计类脚本的退出码是有意义的：**0 = 通过，非 0 = 有问题**，可以直接接进 CI 或 pre-commit。
本仓库自己就接了（见 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)）：在 Linux 上
用 Python 3.9 与 3.12 各跑一遍「泄露扫描 → 词表自洽 → 模拟安装 → 全量体检」。

---

## 配置与自定义

**唯一配置源：`.dsh/wiki.config.json`**（改完保存即生效，没有第二步）

| 想改什么 | 改哪里 |
|---|---|
| 知识库名字、语言 | `wiki_name`、`language` |
| 目录名（`wiki/`、`raw/`、收件箱、归档区） | `dirs.*` |
| 根目录文件名（`index.md` / `log.md` / `TAGS.md`） | `files.*` |
| 五类页面的目录与 `type` 对应关系 | `wiki_types` |
| 概念地图文件名 | `canvas.*` |
| 周报的领域分区 | `domains` |
| venv 位置 | `python.*` |

**Tag 词表：`.dsh/tag-vocab.json`** —— 词表是**数据**，不是代码。七个分面（domain / task / modality / method / challenge / data / meta）的叶节点与中文释义都在这里；`map` 用来登记历史别名与近义词的归一化映射。改完按「`--check` → `--emit-doc` → `tag_apply.py` → `tag_audit.py`」四步走。

**库根自动探测**：如果你把知识库放在一个更大的 Obsidian 库里（比如 `my-vault/notes/`），`vault_prefix` 保持 `"auto"` 即可 —— 脚本会向上找 `.obsidian/` 并自动算出 `notes/` 这个前缀，写进 `.canvas` 的路径永远是对的。也可以显式写死。

---

## Python 依赖（可选）

上面「运行环境」表里的必装项只有 Python 本身。这三个是**可选**的，只有用到 PDF 公式提取才需要：

| 依赖 | 谁需要 | 没有它 |
|---|---|---|
| PyMuPDF | `extract_pdf.py`（PDF 正文抽取） | 摄入 PDF 时正文走不了自动路径，脚本打印安装指引 |
| Pillow | `crop_equations.py`（公式区域裁剪） | 扫描版 PDF / 公式核对只能整页看 |
| LibreOffice Kit（DSH 的 `office-docx` 技能提供路径） | 公式区域渲染 | 同上 |

把可变依赖关在项目 venv 里，**不污染系统 Python**：

```bash
python -m venv .dsh/venv
# Windows:      .dsh\venv\Scripts\python.exe -m pip install -r .dsh/requirements.txt
# macOS/Linux:  .dsh/venv/bin/python       -m pip install -r .dsh/requirements.txt
```

或者一步到位：`python .dsh/scripts/setup_wiki.py --venv`。

缺依赖时脚本不会崩：会打印精确的安装指引并以退出码 1 退出。

---

## 设计原则

1. **配置优先于代码**：仓库里没有一处绝对路径、盘符或用户名。所有位置由 `.dsh/scripts/wiki_env.py` 从脚本自身位置推导，配置只描述「相对结构」。
2. **词表是数据**：tag 词表放在 JSON 里，才能被审计、被迁移、被 diff。放在 Python 常量里就只能靠人肉守规矩。
3. **不可变层是底线**：`raw/` 只读只归档。事实来源不被「顺便优化」污染，是知识库能长期可信的前提。
4. **收尾动作必须显式**：更新 `index.md`、追加 `log.md`、重生成 Canvas 是写页面的**一部分**，不是可选礼貌。
5. **缺依赖要优雅退化**：能降级就降级，不能降级就给出可复制的修复命令 —— 而不是 traceback。
6. **审计用退出码说话**：`0 / 非 0` 比「看起来没问题」可靠。

---

## 方法论出处

本工具包的**基础方法论来自 Andrej Karpathy 的 [`llm-wiki.md`](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**。

那是一份 "idea file"——刻意写得抽象，只讲 pattern、不讲实现，作者本人的用法是
「直接把它丢给你的 LLM agent，让 agent 和你一起把细节长出来」。**本仓库就是它的一个具体实例化**：
把抽象 pattern 落成目录契约、技能、脚本和一份开箱即用的安装流程。

> 📛 **三个名字别混**（它们会同时出现在文档里）：
>
> | 名字 | 指什么 | 在哪 |
> |---|---|---|
> | **ScholarWiki Kit** | 本工具包 / 这个仓库 | README、文档、`LICENSE` |
> | **LLM Wiki** | Karpathy 的**方法论**名；本仓库是它的一个实现 | `AGENTS.md` 的角色定义、本节的对照表 |
> | `wiki_name` | **你自己**知识库的名字，显示在概念地图画布标题里 | `.dsh/wiki.config.json`，默认 `科研 Wiki` |

### 原方法论 → 本工具包的对应关系

| `llm-wiki.md` 里的概念 | 在本工具包中 |
|---|---|
| **三层架构**：Raw sources（不可变，唯一真相来源）／ The wiki（LLM 拥有并维护）／ The schema（告诉 LLM 怎么维护） | `raw/` ／ `wiki/` ／ `AGENTS.md`。「不可变层」这条边界与措辞直接沿用原文档 |
| **三个操作**：Ingest / Query / Lint | **同名的三个技能**：`/ingest`、`/query`、`/lint` |
| **`index.md`**：内容导向的目录，回答提问前先读它定位 | `index.md`，五个固定段落，每次写入必须同步更新 |
| **`log.md`**：时间导向的 append-only 记录；`## [日期] ingest \| 标题` 前缀可被 unix 工具直接解析 | `log.md`，同款格式，操作类型限定为 ingest / query / lint |
| **schema 是"让 LLM 成为有纪律的 wiki 维护者、而不是通用聊天机器人"的关键配置文件** | `AGENTS.md`——本仓库把它写到了可直接执行的粒度（每个收尾动作、每条命名规则都有硬性要求） |
| 「Obsidian 是 IDE，LLM 是程序员，wiki 是代码库」 | 与 Obsidian 的关系完全照此设计：双链、关系图谱、`.canvas` 概念地图 |
| 「原子化的 wiki 是持久的、会复利增长的产物」 | 所有校验脚本（索引一致性、死链、孤儿页、Canvas 同步）都是为了让它**长期**不腐化 |
| 可选的 CLI 工具（搜索等） | 13 个脚本：路径自省、骨架初始化、tag 审计、概念地图生成、PDF 公式提取、环境体检、泄露扫描 |

### 原方法论之上，本仓库补的工程约束

原文档明确说「具体实现取决于你的领域、偏好和 LLM 选择，上面提到的一切都是可选、可拆的」。
以下是这个实例化自己加的：

- **Tag 受控词表**：七分面 + 封闭词表 + 审计与迁移脚本（原文档没有标签体系）；
- **概念分层与概念地图**：母页/子页两级结构，配 `gen_canvas.py` 生成带结构指纹的 Canvas；
- **可执行的校验**：论文页模板、索引一致性、死链与孤儿页、Canvas 同步、词表合规——
  全部**用退出码说话**，可以接进 CI；
- **PDF 公式流水线**：arXiv/DOI 取 LaTeX 真值 → 抽取正文 → 按 bbox 裁公式小图核对，
  让「摄入一篇论文」在公式上不打折；
- **零硬编码**：目录名、词表、领域全部配置化，装到任何机器、任何库上都能跑。

> 原文档是**想法**，本仓库是**其中一个实现**——两者不冲突。如果你想要另一种形状，
> 最该读的其实是原文档本身；把它丢给你的 agent，让它按你的领域长出一套。

---

## 文档

- **[`docs/MANUAL.md`](docs/MANUAL.md) —— 用户手册（新手从这里开始，从零讲到进阶）**
- [`AGENTS.md`](AGENTS.md) —— 完整架构契约（也是安装后给 AI 读的那份）
- [`docs/INSTALL.md`](docs/INSTALL.md) —— 安装细节、目录布局、故障排查
- [`docs/CUSTOMIZE.md`](docs/CUSTOMIZE.md) —— 改目录名 / 换词表 / 换领域 / 加技能
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) —— 数据流与脚本地图
- [`TAGS.md`](TAGS.md) —— 内置 tag 受控词表（随包附带的种子词表）

---

## 许可

[MIT](LICENSE)。随便用，改了也不用告诉我 —— 但如果你把它用出花来了，欢迎开 issue 说说。
