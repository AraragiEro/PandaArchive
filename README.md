# PandaArchive

FRT (Fraternity/凛冬) 联盟数据自动收集爬虫。

## 功能

- **联盟规则**: 从 [FRT Wiki](https://wiki.winterco.org/zh/rules/start) 爬取联盟规则文档，支持增量更新
- **联盟公司**: 从 FRT Wiki 和 [Dotlan](https://evemaps.dotlan.net/alliance/Fraternity./corporations) 爬取公司信息并整合

## 依赖

- Python >= 3.8
- requests >= 2.28.0
- beautifulsoup4 >= 4.11.0

使用 [uv](https://github.com/astral-sh/uv) 管理依赖：

```bash
uv sync
```

## 使用

### 运行所有爬虫

```bash
uv run run_all.py
```

输出统一整理到 `output/` 目录。

### 单独运行

```bash
# 规则爬虫（增量更新）
uv run crawl_frt_rules.py

# 规则爬虫（强制全量更新）
uv run crawl_frt_rules.py --force

# 规则爬虫（试运行，不保存文件）
uv run crawl_frt_rules.py --dry-run

# 公司爬虫
uv run crawl_frt_corp.py
```

### 运行选项

```bash
# 跳过规则爬取
uv run run_all.py --skip-rules

# 跳过公司爬取
uv run run_all.py --skip-corp

# 不清空输出目录
uv run run_all.py --no-clean
```

## 项目结构

```
PandaArchive/
├── crawl_frt_rules.py      # 规则爬虫
├── crawl_frt_corp.py       # 公司爬虫
├── run_all.py              # 主运行脚本
├── frt_rules/              # 规则爬虫输出（按分类）
├── frt_corp/               # 公司爬虫输出
├── output/                 # 主运行脚本汇总输出
├── pyproject.toml          # 项目配置
└── uv.lock                 # 锁定依赖版本
```

## License

[MIT](LICENSE)
