# Category 1: CLI 书签管理器 "bmk"

## 任务描述

构建一个 Python CLI 书签管理工具 "bmk"，使用 SQLite 存储，支持标签、模糊搜索、导入导出。

## 完整规格

### 存储

- SQLite 数据库: `~/.bmk/bookmarks.db`
- Schema: `bookmarks(id INTEGER PRIMARY KEY, url TEXT UNIQUE, title TEXT, description TEXT, tags TEXT, created_at TEXT, updated_at TEXT)`
- Tags 以逗号分隔存储，Python 层面暴露为 list

### CLI 命令 (使用 argparse 或 click)

| 命令 | 说明 |
|------|------|
| `bmk add <url> [--title T] [--tags t1,t2] [--desc D]` | 添加书签（未指定 title 时自动抓取） |
| `bmk list [--tag T] [--limit N] [--sort date\|title]` | 列出书签，可选过滤 |
| `bmk search <query>` | 模糊搜索 url/title/description/tags |
| `bmk delete <id>` | 按 ID 删除 |
| `bmk edit <id> [--title T] [--tags t1,t2] [--desc D]` | 编辑字段 |
| `bmk tags` | 列出所有标签及计数 |
| `bmk export [--format json\|csv\|html] [--output FILE]` | 导出书签 |
| `bmk import <file> [--format json\|csv]` | 导入书签（按 URL 去重） |
| `bmk stats` | 显示统计信息 |

### 质量要求

- 所有函数有类型注解
- 公共函数有 docstrings
- 错误处理: 无效 URL、缺失 DB、网络失败、URL 重复
- 模糊搜索使用 `difflib.SequenceMatcher`（避免额外依赖）

### 测试要求

- pytest 测试 ≥ 8 个
- 覆盖: add/list/search/delete/export-import 往返/tags/error cases
- 使用 `tmp_path` fixture 隔离 DB
- 不发起真实 HTTP（mock title fetching）

### 项目结构

```
bmk/
├── pyproject.toml
├── README.md
├── src/bmk/
│   ├── __init__.py
│   ├── cli.py        # CLI 入口
│   ├── db.py         # SQLite 操作
│   ├── models.py     # 数据类
│   ├── search.py     # 模糊搜索
│   └── io.py         # 导入导出
└── tests/
    ├── __init__.py
    └── test_bmk.py
```

### 可安装性

`pip install -e .` 后可直接运行 `bmk` 命令。

## 统一 Prompt

```
Build a Python CLI bookmark manager called "bmk" with the following requirements:

1. SQLite storage at ~/.bmk/bookmarks.db
2. Commands: add, list, search (fuzzy), delete, edit, tags, export (json/csv/html), import (json/csv), stats
3. Tag system with comma-separated storage
4. Auto-fetch page title when not provided (mock-friendly)
5. Fuzzy search using difflib.SequenceMatcher
6. Type annotations on all functions, docstrings on public functions
7. Error handling for invalid URLs, missing DB, network failures, duplicates
8. pytest test suite with >= 8 tests using tmp_path, no real HTTP calls
9. Project structure: pyproject.toml + src/bmk/ layout + tests/
10. Must be installable via `pip install -e .` and runnable as `bmk`

Create all files and ensure tests pass. Working directory: {WORK_DIR}
```

## 验证命令

```bash
./scripts/verify-cat1.sh <project-dir>
```

## 评分标准

| 维度 | 0-3 分 | 4-6 分 | 7-8 分 | 9-10 分 |
|------|--------|--------|--------|---------|
| 正确性 | <3 命令可用 | 5-6 命令可用 | 全部可用有小 bug | 全部完美运行 |
| 完整性 | 缺 >3 功能 | 缺 1-2 功能 | 全部功能，微小缺失 | 全部功能 + 额外 |
| 质量 | 无类型、无文档 | 部分类型 | 类型+结构良好 | 整洁、地道 Python 3.12 |
| 测试 | 0-2 测试 | 3-5 测试通过 | 6-8 测试覆盖好 | 8+ 测试全过含边界 |
