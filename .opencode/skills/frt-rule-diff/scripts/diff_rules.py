#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRT 规则 diff 摘要生成器

比较两次 Git 提交之间 frt_rules/ 目录下 Markdown 文件的变化，
过滤掉仅元信息（爬取时间、Permalink rev、生成时间）变更的伪变化，
输出按分类组织的变更摘要。

用法:
    python diff_rules.py                    # 比较最近两次提交
    python diff_rules.py HEAD~2 HEAD~1      # 比较指定两次提交
    python diff_rules.py --json             # 输出 JSON 格式
"""

import subprocess
import re
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict


# 元信息变化模式（这些变化不计入实质性变更）
# 直接匹配 diff 行（带 +/− 前缀），允许前导空格和 > 引用标记
META_PATTERNS = [
    re.compile(r"^[+-]\s*>?\s*爬取时间:\s*\d{4}-\d{2}-\d{2}"),
    re.compile(r"^[+-]\s*>?\s*生成时间:\s*\d{4}-\d{2}-\d{2}"),
    re.compile(r"^[+-]\s*\[Permalink\]\([^)]*\?rev=\d+\)"),
]


def run_git_diff(commit1: str, commit2: str, rules_dir: str = "frt_rules") -> str:
    """获取两次提交之间规则文件的 diff"""
    cmd = ["git", "diff", f"{commit1}..{commit2}", "--", f"{rules_dir}/"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore"
    )
    if result.returncode != 0:
        print(f"错误: git diff 失败: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def parse_diff(diff_text: str) -> dict[str, list[str]]:
    """将 diff 文本按文件切分"""
    files = {}
    current_file = None
    current_lines = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current_file:
                files[current_file] = current_lines
            # 提取文件名，支持带引号的 Unicode 路径
            # diff --git a/path b/path
            # diff --git "a/\xxx\xxx/path.md" "b/\xxx\xxx/path.md"
            match = re.search(r"b/(.+?\.md)", line)
            current_file = match.group(1) if match else None
            current_lines = []
        elif current_file is not None:
            current_lines.append(line)

    if current_file:
        files[current_file] = current_lines

    return files


def is_meta_only_change(file_lines: list[str]) -> bool:
    """判断文件的变更是否只有元信息变化"""
    non_meta = []

    for line in file_lines:
        if (line.startswith("+") and not line.startswith("+++")) or (
            line.startswith("-") and not line.startswith("---")
        ):
            if not any(p.match(line) for p in META_PATTERNS):
                non_meta.append(line)

    return len(non_meta) == 0


def decode_git_path(path: str) -> str:
    """解码 git diff 输出的八进制转义路径（如 \\347\\224\\237 -> 生）"""
    result = []
    i = 0
    octal_bytes = []

    while i < len(path):
        if path[i] == "\\" and i + 3 < len(path) and path[i + 1 : i + 4].isdigit():
            octal_bytes.append(int(path[i + 1 : i + 4], 8))
            i += 4
        else:
            if octal_bytes:
                result.append(bytes(octal_bytes).decode("utf-8", errors="replace"))
                octal_bytes = []
            result.append(path[i])
            i += 1

    if octal_bytes:
        result.append(bytes(octal_bytes).decode("utf-8", errors="replace"))

    return "".join(result)


def extract_category(filepath: str) -> str:
    """从文件路径提取分类"""
    decoded = decode_git_path(filepath)
    parts = Path(decoded).parts
    if len(parts) >= 2:
        return parts[-2]
    return "其他"


def extract_title(filepath: str) -> str:
    """从文件路径提取标题"""
    decoded = decode_git_path(filepath)
    return Path(decoded).stem


def summarize_changes(filepath: str, file_lines: list[str]) -> dict:
    """生成单个文件的变更摘要"""
    added = []
    removed = []

    for line in file_lines:
        if line.startswith("+") and not line.startswith("+++"):
            if not any(p.match(line) for p in META_PATTERNS):
                text = line[1:].strip()
                if text:
                    added.append(text)
        elif line.startswith("-") and not line.startswith("---"):
            if not any(p.match(line) for p in META_PATTERNS):
                text = line[1:].strip()
                if text:
                    removed.append(text)

    return {
        "file": filepath,
        "category": extract_category(filepath),
        "title": extract_title(filepath),
        "added_lines": added,
        "removed_lines": removed,
        "net_changes": len(added) - len(removed),
    }


def get_recent_commits(n: int = 10) -> list[str]:
    """获取最近的 n 次提交 hash"""
    result = subprocess.run(
        ["git", "log", "--oneline", f"-{n}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    lines = [l.split()[0] for l in result.stdout.strip().splitlines() if l.strip()]
    return lines


def main():
    parser = argparse.ArgumentParser(
        description="FRT 规则 diff 摘要生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python diff_rules.py                    # 比较最近两次提交
  python diff_rules.py HEAD~2 HEAD~1      # 比较指定提交
  python diff_rules.py --json             # 输出 JSON
        """,
    )
    parser.add_argument(
        "commits", nargs="*", help="要比较的两个提交 (默认: 最近两次)"
    )
    parser.add_argument(
        "--json", action="store_true", help="输出 JSON 格式而非 Markdown"
    )
    parser.add_argument(
        "--dir", default="frt_rules", help="规则文件目录 (默认: frt_rules)"
    )

    args = parser.parse_args()

    # 确定比较的提交
    if len(args.commits) == 0:
        commits = get_recent_commits(2)
        if len(commits) < 2:
            print("错误: 提交历史不足两次", file=sys.stderr)
            sys.exit(1)
        commit1, commit2 = commits[1], commits[0]
    elif len(args.commits) == 2:
        commit1, commit2 = args.commits
    else:
        print("错误: 请提供 0 或 2 个提交参数", file=sys.stderr)
        sys.exit(1)

    print(f"比较: {commit1} .. {commit2}", file=sys.stderr)

    diff_text = run_git_diff(commit1, commit2, args.dir)
    if not diff_text.strip():
        print("未发现变化。")
        return

    file_diffs = parse_diff(diff_text)
    changes = []

    for filepath, lines in file_diffs.items():
        if filepath.endswith("README.md") or filepath.endswith(".changes.json"):
            continue
        if is_meta_only_change(lines):
            continue
        changes.append(summarize_changes(filepath, lines))

    if not changes:
        print("未发现实质性内容变化（所有变更均为元信息更新）。")
        return

    if args.json:
        result = {
            "commit_range": f"{commit1}..{commit2}",
            "total_files": len(changes),
            "changes": changes,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Markdown 输出
    print(f"## 联盟规定变化总结（`{commit1}` → `{commit2}`）\n")
    print(f"共 **{len(changes)}** 份文档发生实质性内容更新：\n")

    # 按分类分组
    by_category = defaultdict(list)
    for c in changes:
        by_category[c["category"]].append(c)

    for category in sorted(by_category.keys()):
        items = by_category[category]
        print(f"### {category}\n")
        for item in items:
            print(f"#### {item['title']}")
            if item["removed_lines"]:
                print("\n**删除**:")
                for line in item["removed_lines"][:20]:  # 限制行数
                    print(f"- {line}")
                if len(item["removed_lines"]) > 20:
                    print(f"- ... 等共 {len(item['removed_lines'])} 行删除")
            if item["added_lines"]:
                print("\n**新增/修改**:")
                for line in item["added_lines"][:20]:
                    print(f"- {line}")
                if len(item["added_lines"]) > 20:
                    print(f"- ... 等共 {len(item['added_lines'])} 行新增")
            print()


if __name__ == "__main__":
    main()
