# 自定义

三件事最容易改，也最值得改：**目录名**、**tag 词表**、**领域分区**。

---

## 1. 改目录名 / 文件名

全部在 `.dsh/wiki.config.json`，改完保存即生效，没有第二步。

```json
{
  "dirs": {
    "wiki": "wiki",
    "raw": "raw",
    "inbox": "raw/research",
    "archive": { "papers": "raw/papers", "book": "raw/book", "...": "..." }
  },
  "files": { "index": "index.md", "log": "log.md", "tags_doc": "TAGS.md", "vocab": ".dsh/tag-vocab.json" },
  "wiki_types": { "papers": "paper", "concepts": "concept", "...": "..." }
}
```

要点：

- **`wiki_types` 的键就是 `wiki/` 下的子目录名**，值是 frontmatter 里的 `type`。
  改目录名要连着这里一起改，否则 lint 的「type 与目录匹配」检查会全线飘红。
- `dirs.inbox` 是 ingest 的唯一入口；`dirs.archive` 是摄入后的归档目标，键名会被
  归档规则引用（论文 → `papers`，书 → `book`，等等）。
- 改完跑一次 `python .dsh/scripts/setup_wiki.py` 建出新目录，
  再跑 `python .dsh/scripts/wiki_env.py --paths` 确认解析结果。

### 库根前缀（`.obsidian` 不在工作区根时）

如果你把知识库放在一个更大的 Obsidian 库里：

```
my-vault/               ← .obsidian/ 在这里（库根）
└── notes/              ← 工作区根（.dsh/ 在这里）
```

`vault_prefix` 保持 `"auto"` 即可，脚本会向上找到 `.obsidian/` 并算出前缀 `notes/`。
写进 `.canvas` 的路径会自动带上它。

不想用自动探测就显式写死：`"vault_prefix": "notes"`；
若工作区本身就是库根：`"vault_prefix": ""`。

---

## 2. 换 tag 词表

词表在 `.dsh/tag-vocab.json` —— **它是数据，不是代码**，所以能被审计、被迁移、被 diff。

```json
{
  "facets": {
    "domain":    { "desc": "领域与平台：…", "hint": "这一页服务于哪个应用/平台？" },
    "task":      { "desc": "任务：…",       "hint": "这一页的输出是什么？" }
  },
  "role_tags": ["母概念", "子概念"],
  "canonical": {
    "domain": { "llm": "大语言模型", "robotics": "机器人" },
    "task":   { "detection": "目标检测" }
  },
  "map": {
    "大模型": ["domain/llm"],
    "detection-task": ["task/detection"]
  },
  "page_overrides": {}
}
```

- **`facets` 的键顺序就是排序顺序**，七个分面（domain → task → modality → method →
  challenge → data → meta）的顺序不要动，`order_tags()` 依赖它。
- **`role_tags` 固定两个**，不带分面前缀，且必须是 `tags` 的第一项 ——
  `gen_canvas.py` 与 lint 检查 7 认字面值，改名会连带改坏概念分层。
- **`canonical`** 是允许出现在页面里的规范 tag 全集，每个分面一组 `叶节点: 中文释义`。
- **`map`** 是历史/别名 → 规范 tag 的归一化映射。一条来源可以映射到多个规范 tag
  （用于把 `cross-modal-fusion` 这种复合历史 tag 拆成 `modality/multimodal` + `method/feature-fusion`）。
  空数组 `[]` 表示「刻意删除这个 tag」。
- **`page_overrides`** 是逐页修剪表：当机械映射结果超过 8 个 tag 的硬上限时，
  在这里显式声明该页要剔除哪些。

### 换成一个完全不同领域的词表

1. 备份：`cp .dsh/tag-vocab.json .dsh/tag-vocab.backup.json`；
2. 只改 `canonical` 的叶节点与 `map`（保持 7 个分面名不变）；
3. `python .dsh/scripts/tag_vocab.py --check` —— 必须 0。
   它会报「规范 tag 无任何映射来源（死词条）」，意思是每个叶节点至少要在 `map` 里
   被某个来源词指到，否则审计时统计不到它；
4. `python .dsh/scripts/tag_vocab.py --emit-doc` 刷新 `TAGS.md`；
5. `python .dsh/scripts/tag_audit.py` 复核。

### 页面上已经写了一堆旧 tag

那是 `map` 的用武之地，**不要手工逐页改**：

```bash
python .dsh/scripts/tag_apply.py              # 预演：只报告会怎么改
python .dsh/scripts/tag_apply.py --apply      # 写盘，自动备份到 .dsh/tmp/tags-backup-*.json
python .dsh/scripts/tag_verify_migration.py   # 独立复核：备份 → 重新推导 → 与磁盘逐页比对
python .dsh/scripts/tag_audit.py              # 退出码必须 0
```

改错了就回滚：`python .dsh/scripts/tag_apply.py --rollback .dsh/tmp/tags-backup-<时间戳>.json`。

> `tag_apply.py` 只改 `tags:` 那一行，其余字节原样保留（走 `read_bytes`/`write_bytes`），
> 连 CRLF 行尾都不会被归一化 —— 所以它对 git diff 很友好。

---

## 3. 改领域分区（周报 / 速报）

```json
{ "domains": ["CV", "NLP", "LLM", "RL", "机器人"] }
```

改完跑 `python .dsh/scripts/setup_wiki.py` 建出 `周报/<域>/` 子目录。
留空数组则跳过周报相关功能，不影响其它部分。

---

## 4. 改知识库名字与语言

```json
{ "wiki_name": "我的研究库", "language": "zh-CN" }
```

`wiki_name` 会出现在概念地图的画布标题里。`language` 目前只影响文档表述
（agent 的行为由 `AGENTS.md` 的「语言设定」决定，改了配置记得同步那句话）。

---

## 5. 加第四个技能

技能就是目录里的一份 Markdown：

```
.dsh/skills/<技能名>/SKILL.md
```

```markdown
---
name: <技能名>
description: 一句话说清「什么时候该用我」——这是技能被自动选中的唯一依据，写得越具体越好。
user-invocable: true
---

# <技能名>

（正文：触发条件、步骤、模板、硬约束）
```

约定：

- 目录名 = frontmatter 的 `name`；
- `description` 里要写清楚触发词与 slash 命令（`/xxx`）；
- 技能要遵守同一份 `AGENTS.md` 契约，否则产出物结构会漂；
- 路径不要写死：让 agent 先跑 `python .dsh/scripts/wiki_env.py --paths`。

加完在 `AGENTS.md` 的「Skills 调度指引」里补一段，agent 才知道什么时候用它。

---

## 6. 改解释器策略

`.dsh/wiki.config.json`：

```json
{ "python": { "venv": ".dsh/venv", "requirements": ".dsh/requirements.txt" } }
```

脚本解析顺序：`WIKI_WORKSPACE` 环境变量 → `.dsh/venv`（Windows 找 `Scripts/python.exe`，
其它平台找 `bin/python`）→ 当前解释器。

**不要把包装进系统 Python。** PDF 抽取的依赖只装在项目 venv 里，
这样换机器、换 harness 都不会互相污染。

---

## 7. 其他可改的地方

| 想改 | 位置 |
|---|---|
| 版权署名 | `LICENSE` **和** `.dsh/LICENSE` 第一行（两处必须一致，`repo_lint.py` 会校验） |
| 仓库地址（安装提示词里的 URL） | `README.md`、`docs/INSTALL.md`、`docs/MANUAL.md`、`CHANGELOG.md` 全文替换 |
| 概念地图文件名 | `.dsh/wiki.config.json` 的 `canvas` |
| 论文页模板要求（8 项判定的具体条文） | `.dsh/scripts/check_paper_template.py` 顶部的判定说明 + 正则 |
| 日志允许的操作类型 | `AGENTS.md` 的「log.md」段 + 三个技能里的写入格式 |
