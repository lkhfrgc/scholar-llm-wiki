# 贡献指南

欢迎提交 issue 与 PR。这个工具包的目标是**「装到任何机器、任何知识库上都能直接跑」**，
所以下面几条是硬约束，PR 会按这个标准 review。

## 硬约束

1. **零硬编码**：不允许出现绝对路径、盘符、用户名、本机目录名。
   所有路径必须经由 `.dsh/scripts/wiki_env.py` 解析。
   提交前跑：

   ```bash
   python .dsh/scripts/repo_lint.py
   ```

   退出码必须是 0。文档确实需要展示"路径的形状"时，在该行加 `repo-lint:ignore` 标记。

2. **配置优先于代码**：新的可变项（目录名、文件名、领域、命名前缀）加到
   `.dsh/wiki.config.json` 并在 `wiki_env.DEFAULTS` 里给默认值，不要写成常量。

3. **词表是数据**：tag 相关改动只改 `.dsh/tag-vocab.json`，
   引擎 `tag_vocab.py` 不应出现具体词条。

4. **只读审计 + 退出码说话**：校验类脚本不改文件、`0 = 通过`、支持 `--json`。
   要写盘的脚本必须支持预演（默认不写），并且**幂等**。

5. **可选项优雅退化**：缺第三方依赖时打印可复制的修复命令，退出码 1，不要 traceback。

6. **UTF-8 无 BOM**，Python ≥ 3.9 兼容。

## 提交前自检

```bash
python .dsh/scripts/repo_lint.py               # 泄露与格式
python .dsh/scripts/tag_vocab.py --check       # 词表自洽
python .dsh/scripts/selfcheck.py               # 环境与骨架
python .dsh/scripts/gen_canvas.py --check      # 画布同步
```

## 目录约定

| 位置 | 放什么 |
|---|---|
| `.dsh/scripts/` | 可执行脚本（一个职责一个文件） |
| `.dsh/skills/<name>/SKILL.md` | 技能：frontmatter 的 `description` 决定它何时被选中 |
| `.dsh/wiki.config.json` | 唯一配置源 |
| `.dsh/tag-vocab.json` | tag 词表数据 |
| `docs/` | 面向使用者的文档 |
| `templates/` | `setup_wiki.py` 用来生成骨架的模板 |

## 新增技能的检查清单

- [ ] 目录名 = frontmatter 的 `name`
- [ ] `description` 写清触发词与 slash 命令（这是被自动选中的唯一依据）
- [ ] 正文里的路径不写死，先让 agent 跑 `wiki_env.py --paths`
- [ ] 遵守 `AGENTS.md` 契约（五类页面、frontmatter、`## 关联连接`、tag 词表）
- [ ] 在 `AGENTS.md` 的「Skills 调度指引」里登记

## 首次发布到 GitHub

仓库已经带好 `.gitignore`、`LICENSE` 与 CI 配置，直接推即可：

```bash
cd llm-wiki-kit
git init -b main
git add -A
git commit -m "feat: LLM Wiki Kit v1.0.0"
git remote add origin https://github.com/<你的用户名>/llm-wiki-kit.git
git push -u origin main
```

推之前把仓库里两处占位符换成真值（否则 README 的安装提示词是废的）：

| 位置 | 替换成 |
|---|---|
| `README.md` 里的 `YOUR-NAME`（共 3 处：一句话安装、短版、手工装） | 你的 GitHub 用户名 |
| `CHANGELOG.md` 底部的 release 链接 | 你的仓库地址 |
| `LICENSE` 第一行的署名（可选） | 你的名字或组织 |

`.dsh/tmp/`、`.dsh/venv/`、`__pycache__/` 已被忽略，不会进版本库。

## 报告问题

请附上：

- `python .dsh/scripts/selfcheck.py` 的输出；
- `python .dsh/scripts/wiki_env.py --json` 的输出（**先自行抹掉绝对路径**）；
- 你的 OS 与 Python 版本。
