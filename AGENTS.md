# AGENTS.md

Agentic coding instructions for PandaArchive repository.

## Project Overview

这是一个 Python 爬虫项目，用于收集 FRT (Fraternity) 联盟的相关数据：
- **联盟规则**: 从 FRT Wiki 爬取联盟规则文档
- **联盟公司**: 从 FRT Wiki 和 Dotlan 爬取公司信息

项目使用 uv 作为包管理器，依赖 requests 和 beautifulsoup4。

## Commands

### 运行项目

```bash
# 运行所有爬虫并收集输出
uv run run_all.py

# 单独运行规则爬虫
uv run crawl_frt_rules.py

# 单独运行公司爬虫
uv run crawl_frt_corp.py

# 查看帮助
uv run run_all.py --help
```

### 包管理

```bash
# 添加依赖
uv add <package>

# 添加开发依赖
uv add --dev <package>

# 同步依赖
uv sync
```

### 代码检查与格式化

```bash
# 使用 ruff 检查代码 (如果已安装)
uv run ruff check .

# 使用 ruff 格式化代码
uv run ruff format .
```

## Code Style Guidelines

### General Principles

- 编写清晰、可读性强的代码
- 优先使用显式而非隐式
- 为公共 API 和复杂逻辑添加文档
- 保持函数小而专注

### Python 特定规范

#### Imports
```python
# 分组顺序：标准库 → 第三方 → 本地
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from crawl_frt_rules import FRTWikiCrawler
```

#### Naming Conventions
- **变量/函数**: snake_case (如 `fetch_page`, `output_dir`)
- **类名**: PascalCase (如 `FRTWikiCrawler`)
- **常量**: UPPER_SNAKE_CASE (如 `BASE_URL`)
- **私有方法/变量**: _prefix (如 `_clean_filename`)

#### Type Hints
```python
def fetch_page(self, url: str) -> BeautifulSoup | None:
    """获取页面内容"""
    ...

def extract_data(self, soup: BeautifulSoup) -> dict[str, Any]:
    """提取数据"""
    ...
```

#### Error Handling
```python
try:
    response = self.session.get(url, timeout=30)
    response.raise_for_status()
except requests.RequestException as e:
    print(f"Error fetching {url}: {e}")
    return None
except Exception as e:
    print(f"Unexpected error: {e}")
    raise
```

#### Docstrings
```python
def crawl(self) -> None:
    """
    主爬取流程
    
    流程：
    1. 获取起始页面
    2. 提取侧边栏结构
    3. 爬取各页面内容
    4. 生成索引文件
    """
```

### 爬虫规范

#### 礼貌爬取
- 每次请求间隔至少 1 秒
- 设置合理的 User-Agent
- 处理超时和重试

#### 数据保存
- Markdown 文件使用 UTF-8 编码
- 输出目录自动创建
- 文件命名清理非法字符

## Project Structure

```
PandaArchive/
├── .git/                   # Git 配置
├── .venv/                  # uv 虚拟环境
├── frt_rules/              # 规则爬虫输出
│   ├── README.md
│   ├── structure.json
│   ├── 行政/
│   ├── 军事/
│   ├── 生产/
│   ├── 贸易/
│   ├── 建筑/
│   └── 其他/
├── FRT_corp/               # 公司爬虫输出
│   └── 公司总揽.md
├── output/                 # 主运行脚本输出
├── skills/                 # 技能目录
├── crawl_frt_rules.py      # 规则爬虫脚本
├── crawl_frt_corp.py       # 公司爬虫脚本
├── run_all.py              # 主运行脚本
├── pyproject.toml          # uv 依赖配置
├── uv.lock                 # 锁定依赖版本
├── LICENSE                 # MIT 许可证
├── README.md               # 项目文档
└── AGENTS.md               # 本文件
```

## File Creation Rules

创建新文件时：

1. **添加文件头注释**
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简短描述

详细描述...
"""
```

2. **遵循现有代码风格**
   - 查看相邻文件的模式
   - 保持命名一致性

3. **更新文档**
   - 修改相关脚本时更新 docstring
   - 新功能添加到 README.md

## Dependencies

```toml
[project]
dependencies = [
    "requests>=2.28.0",         # HTTP 请求
    "beautifulsoup4>=4.11.0",   # HTML 解析
]
```

## Version Control

- 提交原子性、逻辑性的更改
- 使用祈使语气写提交信息 ("Add X" 而非 "Added X")
- 不要提交密钥、构建产物或依赖
- 更新 AGENTS.md 当约定变更时

## UV 使用提示

- `uv run` 会自动创建虚拟环境并安装依赖
- `uv.lock` 锁定依赖版本，确保可复现
- 使用 `uv sync` 同步依赖到锁定文件

---

*本文档应随项目发展而更新。当模式固化时更新它。*
