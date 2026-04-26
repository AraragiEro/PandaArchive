#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRT 数据收集主运行脚本

功能：
1. 运行所有子脚本（规则爬虫、公司爬虫、Excel处理器）
2. 收集所有生成的 Markdown 文件
3. 按类型添加前缀（frt_rule_*、frt_corp_*、frt_excel_*）
4. 统一输出到 output/ 文件夹

使用方法:
    python run_all.py              # 运行所有脚本
    python run_all.py --skip-rules # 跳过规则爬取
    python run_all.py --skip-corp  # 跳过公司爬取
    python run_all.py --skip-excel # 跳过Excel处理
"""

import os
import re
import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Set


class FRTCollector:
    """FRT 数据收集主控类"""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 脚本配置
        self.scripts = {
            "rules": {
                "script": "crawl_frt_rules.py",
                "output_dir": "frt_rules",
                "prefix": "frt_rule_",
                "name": "联盟规则",
            },
            "corp": {
                "script": "crawl_frt_corp.py",
                "output_dir": "FRT_corp",
                "prefix": "frt_corp_",
                "name": "联盟公司",
            },
            "excel": {
                "script": "process_excel.py",
                "output_dir": "excel_output",
                "prefix": "frt_excel_",
                "name": "Excel数据",
                "check_exists": False,  # Excel处理是可选的
            },
        }

        # 收集统计
        self.stats = {
            "scripts_run": 0,
            "scripts_success": 0,
            "files_collected": 0,
            "files_copied": 0,
        }

        self.collected_files: List[
            Tuple[str, Path, str]
        ] = []  # (type, source_path, target_name)

        # 读取规则爬虫的变更列表（None 表示未知，回退到全量复制）
        self.changed_rules: Set[str] | None = None
        rules_changes_file = Path(self.scripts["rules"]["output_dir"]) / ".changes.json"
        if rules_changes_file.exists():
            try:
                with open(rules_changes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.changed_rules = set(data.get("changed_files", []))
            except Exception:
                pass

    def run_script(
        self, script_name: str, description: str, check_exists: bool = True
    ) -> bool:
        """运行单个脚本"""
        print(f"\n{'=' * 60}")
        print(f"正在运行: {description}")
        print(f"脚本: {script_name}")
        print(f"{'=' * 60}")

        # 检查脚本是否存在
        if not Path(script_name).exists():
            if check_exists:
                print(f"[FAIL] 脚本不存在: {script_name}")
                return False
            else:
                print(f"[SKIP] 脚本不存在，跳过: {script_name}")
                return True  # 可选脚本不存在不算失败

        try:
            # 使用当前 Python 解释器运行脚本
            result = subprocess.run(
                [sys.executable, script_name],
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
                encoding="utf-8",
                errors="ignore",
            )

            # 输出脚本的标准输出
            if result.stdout:
                print(result.stdout)

            # 检查是否成功
            if result.returncode == 0:
                print(f"[OK] {description} 运行成功")
                return True
            else:
                print(f"[FAIL] {description} 运行失败 (返回码: {result.returncode})")
                if result.stderr:
                    print(f"错误信息: {result.stderr[:500]}")
                return False

        except subprocess.TimeoutExpired:
            print(f"[FAIL] {description} 运行超时")
            return False
        except Exception as e:
            print(f"[FAIL] {description} 运行出错: {e}")
            return False

    def collect_files(
        self, source_dir: Path, prefix: str, file_type: str
    ) -> List[Tuple[str, Path, str]]:
        """收集指定目录下的所有 Markdown 文件"""
        collected = []

        if not source_dir.exists():
            print(f"  警告: 源目录不存在 {source_dir}")
            return collected

        # 递归查找所有 .md 文件
        md_files = list(source_dir.rglob("*.md"))

        for file_path in md_files:
            # 生成目标文件名
            # 保留相对路径结构，但将路径分隔符替换为下划线
            relative_path = file_path.relative_to(source_dir)

            # 处理文件名
            if relative_path.parent != Path("."):
                # 文件在子目录中，将目录结构加入文件名
                parent_parts = "_".join(relative_path.parent.parts)
                new_name = f"{prefix}{parent_parts}_{relative_path.name}"
            else:
                # 文件在根目录
                new_name = f"{prefix}{relative_path.name}"

            # 清理文件名中的非法字符
            new_name = re.sub(r'[<>"/\\|?*]', "_", new_name)
            new_name = re.sub(r"\s+", "_", new_name)  # 空格替换为下划线

            collected.append((file_type, file_path, new_name))
            print(f"  发现: {file_path} -> {new_name}")

        return collected

    def copy_files(self):
        """将所有收集的文件复制到输出目录（规则文件仅复制变更的）"""
        print(f"\n{'=' * 60}")
        print("正在复制文件到输出目录")
        print(f"输出目录: {self.output_dir.absolute()}")
        print(f"{'=' * 60}")

        copied_count = 0
        skipped_count = 0

        for file_type, source_path, target_name in self.collected_files:
            # 规则文件：若已知变更列表，只复制有变更的文件
            if file_type == "rules" and self.changed_rules is not None:
                rel_path = source_path.relative_to(
                    Path(self.scripts["rules"]["output_dir"])
                ).as_posix()
                if rel_path not in self.changed_rules:
                    print(f"  [SKIP] [{file_type}] 未变更: {target_name}")
                    skipped_count += 1
                    continue

            target_path = self.output_dir / target_name

            try:
                shutil.copy2(source_path, target_path)
                copied_count += 1
                print(f"  [OK] [{file_type}] {source_path.name} -> {target_name}")
            except Exception as e:
                print(f"  [FAIL] [{file_type}] 复制失败 {source_path.name}: {e}")

        if skipped_count:
            print(f"\n  跳过 {skipped_count} 个未变更的规则文件")

        return copied_count

    def generate_index(self):
        """生成输出目录的索引文件"""
        index_file = self.output_dir / "README.md"

        # 按类型分组
        files_by_type = {"rules": [], "corp": [], "excel": [], "other": []}

        for file_type, source_path, target_name in self.collected_files:
            if file_type in files_by_type:
                files_by_type[file_type].append(target_name)
            else:
                files_by_type["other"].append(target_name)

        content = f"""# FRT 数据收集输出文件总览

> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 文件统计

- **总文件数**: {len(self.collected_files)}
- **联盟规则文件**: {len(files_by_type["rules"])}
- **联盟公司文件**: {len(files_by_type["corp"])}
- **Excel数据文件**: {len(files_by_type["excel"])}

## 文件列表

### 联盟规则文件 (frt_rule_*)

| 文件名 | 说明 |
|--------|------|
"""

        for filename in sorted(files_by_type["rules"]):
            # 提取说明
            desc = (
                filename.replace("frt_rule_", "").replace(".md", "").replace("_", " ")
            )
            content += f"| {filename} | {desc} |\n"

        content += f"""

### 联盟公司文件 (frt_corp_*)

| 文件名 | 说明 |
|--------|------|
"""

        for filename in sorted(files_by_type["corp"]):
            desc = (
                filename.replace("frt_corp_", "").replace(".md", "").replace("_", " ")
            )
            content += f"| {filename} | {desc} |\n"

        content += f"""

### Excel数据文件 (frt_excel_*)

| 文件名 | 说明 |
|--------|------|
"""

        for filename in sorted(files_by_type["excel"]):
            desc = (
                filename.replace("frt_excel_", "").replace(".md", "").replace("_", " ")
            )
            content += f"| {filename} | {desc} |\n"

        content += """

## 数据来源

- **联盟规则**: https://wiki.winterco.org/zh/rules/start
- **联盟公司**: 
  - https://wiki.winterco.org/zh/corps/start
  - https://evemaps.dotlan.net/alliance/Fraternity./corporations
- **Excel数据**: excel/ 文件夹中的 CSV/Excel 文件

---

*本文档由 FRT 数据收集系统自动生成*
"""

        with open(index_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  已生成索引文件: {index_file}")

    def clean_output(self):
        """清理输出目录"""
        if self.output_dir.exists():
            print(f"\n清理输出目录: {self.output_dir}")
            # 删除所有旧文件，但保留目录
            for item in self.output_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                    print(f"  已删除: {item.name}")
                except Exception as e:
                    print(f"  删除失败 {item.name}: {e}")

        # 重新创建目录
        self.output_dir.mkdir(exist_ok=True)

    def run(
        self,
        skip_rules: bool = False,
        skip_corp: bool = False,
        skip_excel: bool = False,
        clean: bool = False,
    ):
        """主运行流程"""
        print("=" * 60)
        print("FRT 数据收集主程序")
        print("=" * 60)

        # 1. 清理输出目录（默认保留，显式指定 --clean 才清空）
        if clean:
            self.clean_output()

        # 2. 运行脚本
        scripts_to_run = []
        if not skip_rules:
            scripts_to_run.append(("rules", self.scripts["rules"]))
        if not skip_corp:
            scripts_to_run.append(("corp", self.scripts["corp"]))
        if not skip_excel:
            scripts_to_run.append(("excel", self.scripts["excel"]))

        for key, config in scripts_to_run:
            self.stats["scripts_run"] += 1
            check_exists = config.get("check_exists", True)
            success = self.run_script(config["script"], config["name"], check_exists)
            if success:
                self.stats["scripts_success"] += 1

        # 3. 收集文件
        print(f"\n{'=' * 60}")
        print("正在收集文件")
        print(f"{'=' * 60}")

        if not skip_rules:
            rules_files = self.collect_files(
                Path(self.scripts["rules"]["output_dir"]),
                self.scripts["rules"]["prefix"],
                "rules",
            )
            self.collected_files.extend(rules_files)

        if not skip_corp:
            corp_files = self.collect_files(
                Path(self.scripts["corp"]["output_dir"]),
                self.scripts["corp"]["prefix"],
                "corp",
            )
            self.collected_files.extend(corp_files)

        if not skip_excel:
            excel_files = self.collect_files(
                Path(self.scripts["excel"]["output_dir"]),
                self.scripts["excel"]["prefix"],
                "excel",
            )
            self.collected_files.extend(excel_files)

        self.stats["files_collected"] = len(self.collected_files)

        if self.collected_files:
            print(f"\n共收集到 {len(self.collected_files)} 个文件")

            # 4. 复制文件
            copied = self.copy_files()
            self.stats["files_copied"] = copied

            # 5. 生成索引
            self.generate_index()
        else:
            print("\n未收集到任何文件")

        # 6. 输出统计
        print(f"\n{'=' * 60}")
        print("运行统计")
        print(f"{'=' * 60}")
        print(
            f"脚本运行: {self.stats['scripts_success']}/{self.stats['scripts_run']} 成功"
        )
        print(f"文件收集: {self.stats['files_collected']} 个")
        print(f"文件复制: {self.stats['files_copied']} 个")
        print(f"输出目录: {self.output_dir.absolute()}")
        print(f"{'=' * 60}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="FRT 数据收集主程序",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_all.py              # 运行所有脚本
  python run_all.py --skip-rules # 跳过规则爬取
  python run_all.py --skip-corp  # 跳过公司爬取
  python run_all.py --skip-excel # 跳过Excel处理
   python run_all.py --clean      # 清空输出目录
        """,
    )

    parser.add_argument("--skip-rules", action="store_true", help="跳过规则爬虫脚本")

    parser.add_argument("--skip-corp", action="store_true", help="跳过公司爬虫脚本")

    parser.add_argument("--skip-excel", action="store_true", help="跳过Excel处理脚本")

    parser.add_argument(
        "--clean", action="store_true", help="清空输出目录（默认保留已有文件）"
    )

    parser.add_argument(
        "--output", "-o", default="output", help="输出目录（默认: output）"
    )

    args = parser.parse_args()

    if args.skip_rules and args.skip_corp and args.skip_excel:
        print("错误: 不能同时跳过所有脚本")
        return

    collector = FRTCollector(output_dir=args.output)
    collector.run(
        skip_rules=args.skip_rules,
        skip_corp=args.skip_corp,
        skip_excel=args.skip_excel,
        clean=args.clean,
    )


if __name__ == "__main__":
    main()
