#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel/CSV 文件处理器
读取 excel/ 文件夹下的 CSV 和 Excel 文件，转换为 Markdown 文档

支持格式:
- .csv - CSV 文件
- .xlsx, .xls - Excel 文件

输出: excel_output/ 文件夹
"""

import os
import re
import csv
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

# 尝试导入 openpyxl 处理 Excel 文件
try:
    import openpyxl

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    print("警告: 未安装 openpyxl，无法处理 .xlsx 文件")
    print("安装命令: uv add openpyxl")


class ExcelProcessor:
    """Excel/CSV 文件处理器"""

    def __init__(self, input_dir: str = "excel", output_dir: str = "excel_output"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 支持的文件格式
        self.supported_extensions = {".csv", ".xlsx", ".xls"}

        # 统计信息
        self.stats = {
            "files_found": 0,
            "files_processed": 0,
            "files_failed": 0,
            "tables_generated": 0,
        }

    def find_files(self) -> List[Path]:
        """查找所有支持的文件"""
        files = []
        if not self.input_dir.exists():
            print(f"警告: 输入目录不存在 {self.input_dir}")
            return files

        for ext in self.supported_extensions:
            files.extend(self.input_dir.glob(f"*{ext}"))

        self.stats["files_found"] = len(files)
        return sorted(files)

    def read_csv(self, file_path: Path) -> Tuple[List[str], List[List[str]]]:
        """读取 CSV 文件，返回 (表头, 数据行)"""
        headers = []
        rows = []

        # 尝试不同的编码
        encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding, newline="") as f:
                    reader = csv.reader(f)
                    all_rows = list(reader)

                    if all_rows:
                        headers = all_rows[0]
                        rows = all_rows[1:]

                    return headers, rows
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"  使用 {encoding} 读取失败: {e}")
                continue

        raise ValueError(f"无法解码文件: {file_path}")

    def read_excel(self, file_path: Path) -> Tuple[List[str], List[List[str]]]:
        """读取 Excel 文件，返回 (表头, 数据行)"""
        if not HAS_OPENPYXL:
            raise ImportError("未安装 openpyxl，无法读取 Excel 文件")

        headers = []
        rows = []

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            # 默认读取第一个工作表
            ws = wb.active

            # 读取所有行
            all_data = []
            for row in ws.iter_rows(values_only=True):
                all_data.append([str(cell) if cell is not None else "" for cell in row])

            if all_data:
                headers = all_data[0]
                rows = all_data[1:]

            return headers, rows
        except Exception as e:
            raise ValueError(f"读取 Excel 失败: {e}")

    def read_file(self, file_path: Path) -> Tuple[List[str], List[List[str]]]:
        """根据文件类型读取数据"""
        ext = file_path.suffix.lower()

        if ext == ".csv":
            return self.read_csv(file_path)
        elif ext in {".xlsx", ".xls"}:
            return self.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    def clean_cell(self, cell: str) -> str:
        """清理单元格内容，用于 Markdown 表格"""
        if cell is None:
            return ""

        cell = str(cell).strip()
        # 替换 Markdown 表格特殊字符
        cell = cell.replace("|", "\\|")
        cell = cell.replace("\n", "<br>")
        cell = cell.replace("\r", "")
        return cell

    def generate_markdown_table(
        self, headers: List[str], rows: List[List[str]], title: str = ""
    ) -> str:
        """生成 Markdown 表格"""
        # 清理表头
        clean_headers = [self.clean_cell(h) for h in headers]

        # 构建表格
        md_lines = []

        if title:
            md_lines.append(f"### {title}")
            md_lines.append("")

        # 表头
        md_lines.append("| " + " | ".join(clean_headers) + " |")
        # 分隔符
        md_lines.append("| " + " | ".join(["---"] * len(clean_headers)) + " |")

        # 数据行
        for row in rows:
            # 跳过空行
            if not any(cell.strip() for cell in row):
                continue

            # 补齐列数
            row_data = row + [""] * (len(headers) - len(row))
            clean_row = [self.clean_cell(cell) for cell in row_data[: len(headers)]]
            md_lines.append("| " + " | ".join(clean_row) + " |")

        return "\n".join(md_lines)

    def analyze_structure(
        self, headers: List[str], rows: List[List[str]]
    ) -> List[Dict[str, Any]]:
        """分析表格结构，识别多个子表"""
        tables = []
        current_table = None

        for i, row in enumerate(rows):
            # 检查是否是新的子表标题行（通常只有1-2个非空单元格）
            non_empty = [cell.strip() for cell in row if cell.strip()]

            # 如果是新表格的开始（标题行或空行后的标题）
            if len(non_empty) <= 2 and any(cell.strip() for cell in row[:2]):
                # 保存之前的表格
                if current_table and current_table["rows"]:
                    tables.append(current_table)

                # 创建新表格
                title = non_empty[0] if non_empty else f"表 {len(tables) + 1}"
                current_table = {"title": title, "headers": None, "rows": []}
            elif current_table is None:
                # 第一个表格还没有创建
                current_table = {"title": "数据表", "headers": None, "rows": []}
                # 如果这是表头行
                if i == 0 or all(cell.strip() for cell in row[: len(headers) // 2]):
                    current_table["headers"] = row
                else:
                    current_table["rows"].append(row)
            else:
                # 普通数据行
                # 如果还没有设置表头，且这行看起来像表头
                if current_table["headers"] is None:
                    # 检查是否是表头（包含常见的列标题关键词）
                    is_header = any(
                        keyword in str(cell).lower()
                        for cell in row
                        for keyword in ["名称", "群号", "编号", "id", "name", "title"]
                    )
                    if is_header:
                        current_table["headers"] = row
                    else:
                        current_table["rows"].append(row)
                else:
                    current_table["rows"].append(row)

        # 添加最后一个表格
        if current_table and current_table["rows"]:
            tables.append(current_table)

        # 如果没有识别出子表，将整个数据作为一个表
        if not tables:
            tables = [{"title": "数据表", "headers": headers, "rows": rows}]

        return tables

    def process_file(self, file_path: Path) -> str:
        """处理单个文件，返回 Markdown 内容"""
        print(f"\n  处理: {file_path.name}")

        try:
            # 读取文件
            headers, rows = self.read_file(file_path)

            if not headers and not rows:
                print(f"    警告: 文件为空")
                return ""

            # 分析结构
            tables = self.analyze_structure(headers, rows)

            # 生成 Markdown
            md_parts = []

            # 文件标题
            file_title = file_path.stem.replace("-", " ").replace("_", " ")
            md_parts.append(f"## {file_title}")
            md_parts.append("")
            md_parts.append(f"> 来源文件: `{file_path.name}`")
            md_parts.append(
                f"> 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            md_parts.append("")

            # 生成各个子表
            for table in tables:
                table_headers = table["headers"] if table["headers"] else headers
                table_rows = table["rows"]

                if table_headers and table_rows:
                    table_md = self.generate_markdown_table(
                        table_headers, table_rows, table["title"]
                    )
                    md_parts.append(table_md)
                    md_parts.append("")
                    self.stats["tables_generated"] += 1

            self.stats["files_processed"] += 1
            return "\n".join(md_parts)

        except Exception as e:
            print(f"    错误: 处理失败 - {e}")
            self.stats["files_failed"] += 1
            return ""

    def generate_index(self, files_data: List[Tuple[str, str]]) -> str:
        """生成索引文件"""
        content = f"""# Excel 数据汇总

> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> 文件数量: {len(files_data)}

## 目录

"""

        for filename, _ in files_data:
            anchor = filename.replace(" ", "-").replace("_", "-")
            content += f"- [{filename}](#{anchor})\n"

        content += "\n---\n\n"

        # 添加所有内容
        for filename, md_content in files_data:
            content += md_content
            content += "\n\n---\n\n"

        return content

    def process_all(self) -> Path:
        """处理所有文件"""
        print("=" * 60)
        print("Excel/CSV 文件处理器")
        print("=" * 60)

        # 1. 查找文件
        print(f"\n[1/3] 正在查找文件...")
        files = self.find_files()

        if not files:
            print("  未找到任何 CSV/Excel 文件")
            return None

        print(f"  找到 {len(files)} 个文件:")
        for f in files:
            print(f"    - {f.name}")

        # 2. 处理每个文件
        print(f"\n[2/3] 正在处理文件...")
        files_data = []

        for file_path in files:
            md_content = self.process_file(file_path)
            if md_content:
                files_data.append((file_path.stem, md_content))

        # 3. 生成汇总文档
        print(f"\n[3/3] 正在生成文档...")

        if files_data:
            # 生成汇总文件
            index_content = self.generate_index(files_data)
            index_file = self.output_dir / "汇总文档.md"

            with open(index_file, "w", encoding="utf-8") as f:
                f.write(index_content)

            print(f"  已生成: {index_file}")

            # 同时生成单个文件
            for filename, md_content in files_data:
                output_file = self.output_dir / f"{filename}.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(md_content)
                print(f"  已生成: {output_file}")

        # 4. 输出统计
        print(f"\n{'=' * 60}")
        print("处理完成!")
        print(f"找到文件: {self.stats['files_found']}")
        print(f"成功处理: {self.stats['files_processed']}")
        print(f"处理失败: {self.stats['files_failed']}")
        print(f"生成表格: {self.stats['tables_generated']}")
        print(f"输出目录: {self.output_dir.absolute()}")
        print(f"{'=' * 60}")

        return self.output_dir if files_data else None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Excel/CSV 文件处理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python process_excel.py              # 处理所有文件
  python process_excel.py -i data      # 指定输入目录
  python process_excel.py -o output    # 指定输出目录
        """,
    )

    parser.add_argument(
        "-i", "--input", default="excel", help="输入目录（默认: excel）"
    )

    parser.add_argument(
        "-o", "--output", default="excel_output", help="输出目录（默认: excel_output）"
    )

    args = parser.parse_args()

    processor = ExcelProcessor(input_dir=args.input, output_dir=args.output)
    processor.process_all()


if __name__ == "__main__":
    main()
