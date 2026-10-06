# 安装

> 第一次接触这个工具？先看 [用户手册](MANUAL.md)。本文只讲安装本身。

三种方式，任选一种。全程不需要联网装依赖（脚本只用标准库）。

## 前置：运行环境

| 组件 | 必需性 | 作用 |
|---|---|---|
| **DSH（DeepSeek Harness）** | 强烈建议 | 技能宿主：三个技能靠它触发，`AGENTS.md` 靠它自动加载 |
| **Obsidian** | 强烈建议 | 呈现层：双链、关系图谱、概念地图靠它渲染 |
| **Python ≥ 3.9** | 必需 | 全部脚本 |

三者的取舍与降级说明见 [README 的运行环境一节](../README.md#运行环境装之前先看这一段)。

## 方式 A：让 agent 装（推荐）

把 [`README.md`](../README.md#-一句话安装) 里那句「一句话安装」复制给你的 DSH。
它的完整语义是：

1. `git clone` 仓库到临时目录（没有 git 就下载 zip 并解压）；
2. 把 `.dsh/`、`AGENTS.md`、`templates/` **合并式**复制到当前工作区 ——
   已存在的同名文件一律不覆盖，冲突项另存为 `<原文件名>.kit-new`；
3. 运行 `python .dsh/scripts/setup_wiki.py`；
4. 运行 `python .dsh/scripts/selfcheck.py` 并把报告贴回来；
5. 不碰 `raw/` 下的任何文件。

> 若你的知识库已经有自己的 `AGENTS.md`，先看第 3 节「与已有 AGENTS.md 共存」。

## 方式 B：手工装

```bash
git clone https://github.com/lkhfrgc/scholar-llm-wiki /tmp/scholar-llm-wiki
cd /path/to/your-vault

# 只复制这三样；.dsh/ 是目录，复制时要做合并而不是覆盖
cp -rn /tmp/scholar-llm-wiki/.dsh /tmp/scholar-llm-wiki/templates .
cp -n  /tmp/scholar-llm-wiki/AGENTS.md .

python .dsh/scripts/setup_wiki.py
python .dsh/scripts/selfcheck.py
```

Windows PowerShell（`Copy-Item` 不带 `-Force` 即不覆盖）：

```powershell
git clone https://github.com/lkhfrgc/scholar-llm-wiki $env:TEMP\scholar-llm-wiki
Copy-Item $env:TEMP\scholar-llm-wiki\.dsh, $env:TEMP\scholar-llm-wiki\templates . -Recurse
Copy-Item $env:TEMP\scholar-llm-wiki\AGENTS.md .
python .dsh/scripts/setup_wiki.py
python .dsh/scripts/selfcheck.py
```

## 方式 C：直接把这个仓库当工作区

如果你的知识库装在别处、只想拿它当工具，可以在任意目录 `git clone` 本仓库，
然后设置环境变量把脚本指向你的库：

```bash
export WIKI_WORKSPACE=/path/to/your-vault      # Windows: $env:WIKI_WORKSPACE="<你的知识库目录>"
export WIKI_CONFIG=$WIKI_WORKSPACE/.dsh/wiki.config.json
python /path/to/scholar-llm-wiki/.dsh/scripts/tag_audit.py
```

`WIKI_WORKSPACE` 覆盖工作区根，`WIKI_CONFIG` 覆盖配置文件位置。两者都可省略。

---

## 1. 安装后应该看到什么

```
your-vault/
├── AGENTS.md                 ← 从工具包复制
├── templates/                ← 从工具包复制（骨架模板，可删）
├── TAGS.md                   ← setup_wiki.py 生成
├── index.md                  ← setup_wiki.py 从模板生成
├── log.md                    ← 同上
├── wiki/{papers,concepts,connections,questions,syntheses}/
├── raw/{research,papers,book,courses,clips,articles,assets}/
└── .dsh/
    ├── wiki.config.json      ← 唯一配置源
    ├── tag-vocab.json        ← tag 受控词表（数据）
    ├── requirements.txt
    ├── skills/{ingest,query,lint}/SKILL.md
    └── scripts/*.py
```

`python .dsh/scripts/setup_wiki.py` 是**幂等**的：反复跑只会补缺失项，
已存在的 `index.md` / `log.md` / 词表一律跳过。要强制覆盖用 `--force`（会丢内容）。

## 2. 验证安装

```bash
python .dsh/scripts/wiki_env.py --paths     # ① 路径解析对不对
python .dsh/scripts/selfcheck.py            # ② 环境体检（必需项必须全 ✓）
python .dsh/scripts/tag_vocab.py --check    # ③ 词表自洽
python .dsh/scripts/gen_canvas.py --check   # ④ 画布状态
```

按上面的顺序（先 `setup_wiki.py`）跑完，**四个命令都应该退出码 0**。

会出现「非 0 但属正常」的只有一处：**跳过初始化**直接跑 ④ 时会报
`MISSING 概念全景图.canvas`，因为还没有画布。`setup_wiki.py` 会生成它。

## 3. 与已有 AGENTS.md 共存

工具包的 `AGENTS.md` 是**契约文档**，不是启动脚本。若你的工作区已有 `AGENTS.md`：

- 把本包的章节（目录契约、Tag 规范、概念分层、Canvas 同步、Skills 调度）**合并**进你的文件；
- 或在你的 `AGENTS.md` 顶部加一行指路：`架构契约见 AGENTS-wiki.md`，
  然后把本包的文件存为 `AGENTS-wiki.md`。

不要两份并存且互相矛盾 —— agent 会随机挑一份执行。

## 4. 可选依赖

只有 PDF 正文抽取需要第三方库。**插件式安装，不碰系统 Python**：

```bash
python -m venv .dsh/venv
# Windows:      .dsh\venv\Scripts\python.exe -m pip install -r .dsh/requirements.txt
# macOS/Linux:  .dsh/venv/bin/python       -m pip install -r .dsh/requirements.txt
```

或者一步到位：`python .dsh/scripts/setup_wiki.py --venv`。

## 5. 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `wiki_env` 报出的工作区根不对 | `.dsh/scripts/wiki_env.py` 靠自身位置上溯两级推断；若你把脚本挪了位置，用 `WIKI_WORKSPACE` 显式指定 |
| `.canvas` 里卡片显示「未找到引用的文件」 | 库根前缀算错了。跑 `python .dsh/scripts/wiki_env.py --paths` 看 `vault_prefix`；若不对，在 `.dsh/wiki.config.json` 把 `vault_prefix` 从 `"auto"` 改成显式值（如 `"notes"`，或空串表示工作区就是库根） |
| 技能没被 harness 识别 | 确认 `.dsh/skills/<name>/SKILL.md` 存在且首行 frontmatter 有 `name` 与 `description`；重启一次会话 |
| `extract_pdf.py` 报缺 PyMuPDF | 按第 4 节建 venv；脚本会打印精确命令 |
| Windows 控制台中文乱码 | 脚本内部已把 stdout 切到 UTF-8；若仍有问题，`chcp 65001` |
| `tag_audit.py` 报一堆未登记 tag | 那是**有效信号**：说明页面用了词表外的词。按 [`TAGS.md`](../TAGS.md) 的「新增 tag 流程」处理，或把近义词登记进 `map` |
| `gen_canvas.py --check` 报 STALE | 族结构变了但画布没重生成。跑一次不带 `--check` 的命令即可 |

## 6. 卸载

删掉 `.dsh/`、`AGENTS.md`、`templates/`、`TAGS.md` 即可。
`wiki/`、`raw/`、`index.md`、`log.md` 都是你自己的内容，与本工具包无关。
