# LLM Wiki Kit

> 把碎片化资料**编译**成结构化、高度互链的 Obsidian 知识库 —— 一套给 AI agent 用的工作流工具包。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-%E2%89%A53.9-blue.svg)
![Dependencies](https://img.shields.io/badge/deps-stdlib%20only%20(optional%3A%20PyMuPDF%2C%20Pillow)-green.svg)

它不是「笔记模板」，而是一套**可执行的知识库契约**：

- `AGENTS.md` —— 给 AI 的架构规范：目录权限边界、页面分类、命名规则、双链、tag 受控词表、概念分层、Canvas 同步；
- 三个技能（`ingest` / `query` / `lint`）—— 把「摄入资料 → 生成页面 → 维护索引 → 健康巡检」固化成流水线；
- 一沓脚本 —— 路径自省、骨架初始化、tag 审计、概念地图生成、PDF 公式提取、环境自检；
- 一份配置 —— 所有目录名、领域、词表都在 JSON 里，**仓库内零硬编码、零绝对路径**。

---

## 🚀 一句话安装

把下面这一整句发给你的 agent（DeepSeek Harness / Claude Code / Cursor / 任何能读写文件并执行命令的 harness），它会自己完成全部安装：

> **请安装 LLM Wiki Kit：把 `https://github.com/YOUR-NAME/llm-wiki-kit` 克隆到临时目录（没有 git 就下载 zip 解压），将仓库里的 `.dsh/`、`AGENTS.md`、`templates/` 复制到当前工作区（`.dsh/` 按目录合并，任何已存在的同名文件都不要覆盖，冲突项另存为 `<原文件名>.kit-new`），然后依次运行 `python .dsh/scripts/setup_wiki.py` 与 `python .dsh/scripts/selfcheck.py`，把体检报告原样贴给我，并提醒我把待摄入资料放进 `raw/research/`；全程不要修改 `raw/` 下的任何文件。**

<details>
<summary>更短的版本（先试 clone，失败再手工）</summary>

> **克隆 `https://github.com/YOUR-NAME/llm-wiki-kit`，把里面的 `.dsh/` 和 `AGENTS.md` 复制到当前工作区（不要覆盖已有文件），跑 `python .dsh/scripts/setup_wiki.py`，然后把 `selfcheck.py` 的结果给我看。**

</details>

<details>
<summary>不用 agent，手工装（30 秒）</summary>

```bash
git clone https://github.com/YOUR-NAME/llm-wiki-kit /tmp/llm-wiki-kit
cp -r /tmp/llm-wiki-kit/.dsh /tmp/llm-wiki-kit/AGENTS.md /tmp/llm-wiki-kit/templates .   # 合并式复制
python .dsh/scripts/setup_wiki.py
python .dsh/scripts/selfcheck.py
```

Windows PowerShell：

```powershell
git clone https://github.com/YOUR-NAME/llm-wiki-kit $env:TEMP\llm-wiki-kit
Copy-Item $env:TEMP\llm-wiki-kit\.dsh, $env:TEMP\llm-wiki-kit\AGENTS.md, $env:TEMP\llm-wiki-kit\templates . -Recurse
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

python .dsh/scripts/repo_lint.py               # 提交前扫描：绝对路径 / 用户名 / 凭据 / BOM

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

## 依赖

| 依赖 | 谁需要 | 必需性 |
|---|---|---|
| Python ≥ 3.9 | 全部脚本 | 必需 |
| PyMuPDF | `extract_pdf.py`（PDF 正文抽取） | 可选 |
| Pillow | `crop_equations.py`（公式裁剪） | 可选 |
| LibreOffice Kit（harness 提供） | 扫描版 PDF / 公式区域渲染 | 可选 |
| Obsidian | 看双链、图谱、Canvas | 可选（纯 markdown 也能用） |

把可变依赖关在项目 venv 里，**不污染系统 Python**：

```bash
python -m venv .dsh/venv
# Windows:      .dsh\venv\Scripts\python.exe -m pip install -r .dsh/requirements.txt
# macOS/Linux:  .dsh/venv/bin/python       -m pip install -r .dsh/requirements.txt
```

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

## 文档

- [`AGENTS.md`](AGENTS.md) —— 完整架构契约（也是安装后给 AI 读的那份）
- [`docs/INSTALL.md`](docs/INSTALL.md) —— 安装细节、目录布局、故障排查
- [`docs/CUSTOMIZE.md`](docs/CUSTOMIZE.md) —— 改目录名 / 换词表 / 换领域 / 加技能
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) —— 数据流与脚本地图

---

## 许可

[MIT](LICENSE)。随便用，改了也不用告诉我 —— 但如果你把它用出花来了，欢迎开 issue 说说。
