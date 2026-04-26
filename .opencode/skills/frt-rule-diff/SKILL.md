---
name: frt-rule-diff
description: >
  比较 FRT 联盟规则文档在两次 Git 提交之间的实质性内容变化，过滤元信息伪变更，生成按分类组织的变更摘要。
  使用场景：
  (1) 用户要求"总结一下最近联盟规则的变化"
  (2) 用户要求"对比两次提交之间的规则差异"
  (3) 用户要求"查看某份规则文档的变更历史"
  (4) 任何涉及 frt_rules/ 目录下 Markdown 文件 diff 分析的需求
---

# FRT 规则 Diff 摘要

## 快速使用

直接运行脚本，自动比较最近两次提交：

```bash
uv run skills/frt-rule-diff/scripts/diff_rules.py
```

或指定提交：

```bash
uv run skills/frt-rule-diff/scripts/diff_rules.py HEAD~2 HEAD~1
```

## 工作原理

脚本执行以下步骤：

1. `git diff <commit1>..<commit2> -- frt_rules/` 获取规则文件差异
2. 按文件切分 diff
3. **过滤伪变更**：排除仅涉及以下元信息的变化
   - 爬取时间 (`> 爬取时间: YYYY-MM-DD`)
   - 生成时间 (`> 生成时间: YYYY-MM-DD`)
   - Permalink rev (`[Permalink](...?rev=123)`)
4. 对剩余实质性变更按分类（行政/生产/建筑/军事/贸易/其他）分组
5. 输出 Markdown 或 JSON 格式的变更摘要

## 输出格式

### 默认 Markdown

适合直接呈现给用户：

```markdown
## 联盟规定变化总结（`abc1234` → `def5678`）

共 **3** 份文档发生实质性内容更新：

### 行政

#### FRTA管理

**删除**:
- F.A.X联盟有声望不允许下建筑 要求挂靠母团...

**新增/修改**:
- FRTA联盟拥有FRT蓝声望。
- FRTA公司不允许下建筑，公司必须设置为不接受转让建筑。
```

### JSON 模式（`--json`）

适合程序化处理：

```bash
uv run skills/frt-rule-diff/scripts/diff_rules.py --json
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `[commit1] [commit2]` | 要比较的两个 Git 提交，省略则自动取最近两次 |
| `--json` | 输出 JSON 而非 Markdown |
| `--dir <dir>` | 规则文件目录（默认: `frt_rules`） |

## 注意事项

- 自动排除 `README.md` 和 `.changes.json`（索引/状态文件）
- 若所有变更均为元信息更新，脚本会报告"未发现实质性内容变化"
- 每份文档最多显示 20 条增删行，超出用 `... 等共 N 行` 提示
