#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRT Wiki 联盟规则爬虫（支持增量更新）
爬取 https://wiki.winterco.org/zh/rules/start 及其所有子页面
并将内容分类保存为 Markdown 文件

使用方法:
  python crawl_frt_rules.py              # 增量更新（默认）
  python crawl_frt_rules.py --force      # 强制全量更新
  python crawl_frt_rules.py --dry-run    # 试运行，不保存文件
"""

import os
import re
import time
import json
import hashlib
import argparse
from urllib.parse import urljoin, urlparse
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup


class FRTWikiCrawler:
    """FRT Wiki 爬虫类（支持增量更新）"""

    BASE_URL = "https://wiki.winterco.org"
    START_URL = "https://wiki.winterco.org/zh/rules/start"

    def __init__(
        self,
        output_dir: str = "frt_rules",
        incremental: bool = True,
        dry_run: bool = False,
    ):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.incremental = incremental
        self.dry_run = dry_run

        # 加载状态文件
        self.state_file = self.output_dir / ".crawl_state.json"
        self.crawl_state = self.load_state()

        # 存储所有规则页面信息
        self.rules_structure = {}

        # 统计信息
        self.stats = {"total": 0, "new": 0, "updated": 0, "skipped": 0, "failed": 0}

    def load_state(self) -> dict:
        """加载爬取状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_state(self):
        """保存爬取状态"""
        if not self.dry_run:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.crawl_state, f, ensure_ascii=False, indent=2)

    def get_page_hash(self, content: str) -> str:
        """计算页面内容哈希"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def should_update(self, url: str, content: str) -> tuple[bool, str]:
        """
        检查是否需要更新页面
        返回: (是否需要更新, 原因)
        """
        if not self.incremental:
            return True, "强制更新模式"

        page_hash = self.get_page_hash(content)

        if url not in self.crawl_state:
            return True, "新页面"

        old_state = self.crawl_state[url]
        if old_state.get("hash") != page_hash:
            return True, "内容已更改"

        return False, "内容未更改"

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        """获取页面内容并解析"""
        try:
            print(f"    获取: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"    错误: 无法获取 {url} - {e}")
            self.stats["failed"] += 1
            return None

    def extract_sidebar_structure(self, soup: BeautifulSoup) -> dict:
        """从侧边栏提取规则分类结构"""
        structure = {}

        # 查找侧边栏
        sidebar = soup.find("aside", id="dokuwiki__aside")
        if not sidebar:
            print("    警告: 未找到侧边栏")
            return structure

        # 查找所有 panel
        panels = sidebar.find_all(
            "div", class_=lambda x: x and "panel" in x and "panel-default" in x
        )

        current_category = None
        for panel in panels:
            # 查找面板标题
            heading = panel.find("div", class_="panel-heading")
            if heading:
                category_name = heading.get_text(strip=True)
                current_category = category_name
                structure[current_category] = []

            # 查找面板中的链接
            if current_category:
                links = panel.find_all("a", class_="wikilink1")
                for link in links:
                    href = link.get("href", "")
                    title = link.get_text(strip=True)
                    if href and title:
                        full_url = urljoin(self.BASE_URL, href)
                        structure[current_category].append(
                            {"title": title, "url": full_url, "path": href}
                        )

        return structure

    def extract_main_content(self, soup: BeautifulSoup) -> dict:
        """提取页面主要内容"""
        content_data = {"title": "", "content": "", "headings": [], "raw_html": ""}

        # 提取标题
        title_elem = soup.find("h1", class_="page-header")
        if title_elem:
            content_data["title"] = title_elem.get_text(strip=True)

        # 提取主要内容区域
        content_div = soup.find("div", {"itemprop": "articleBody"})
        if not content_div:
            content_div = soup.find("div", id="dokuwiki__content")

        if content_div:
            # 保存原始HTML用于哈希比较（在移除元素之前）
            content_data['raw_html'] = str(content_div)
            
            # 移除不需要的元素
            for elem in content_div.find_all(['script', 'style', 'nav', 'aside']):
                elem.decompose()
            # 移除不需要的元素
            for elem in content_div.find_all(["script", "style", "nav", "aside"]):
                elem.decompose()

            # 提取所有标题作为目录
            headings = content_div.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            for h in headings:
                level = int(h.name[1])
                text = h.get_text(strip=True)
                if text:
                    content_data["headings"].append({"level": level, "text": text})

            # 提取纯文本内容（用于 Markdown）
            content_data["content"] = self.html_to_markdown(content_div)

        return content_data

    def html_to_markdown(self, element) -> str:
        """将 HTML 转换为 Markdown 格式"""
        markdown_lines = []

        for child in element.descendants:
            if child.name == "h1":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"\n# {text}\n")
            elif child.name == "h2":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"\n## {text}\n")
            elif child.name == "h3":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"\n### {text}\n")
            elif child.name == "h4":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"\n#### {text}\n")
            elif child.name == "p":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"{text}\n")
            elif child.name == "ul":
                for li in child.find_all("li", recursive=False):
                    text = li.get_text(strip=True)
                    if text:
                        markdown_lines.append(f"- {text}")
                markdown_lines.append("")
            elif child.name == "ol":
                for idx, li in enumerate(child.find_all("li", recursive=False), 1):
                    text = li.get_text(strip=True)
                    if text:
                        markdown_lines.append(f"{idx}. {text}")
                markdown_lines.append("")
            elif child.name == "a":
                href = child.get("href", "")
                text = child.get_text(strip=True)
                if href and text and not href.startswith("#"):
                    if not href.startswith("http"):
                        href = urljoin(self.BASE_URL, href)
                    markdown_lines.append(f"[{text}]({href})")
            elif child.name == "strong" or child.name == "b":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"**{text}**")
            elif child.name == "em" or child.name == "i":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"*{text}*")
            elif child.name == "code":
                text = child.get_text(strip=True)
                if text:
                    markdown_lines.append(f"`{text}`")
            elif child.name == "pre":
                text = child.get_text(strip=True)
                if text:
                    lines = text.split("\n")
                    markdown_lines.append("```")
                    markdown_lines.extend(lines)
                    markdown_lines.append("```")
                    markdown_lines.append("")

        # 清理并合并内容
        result = "\n".join(markdown_lines)
        # 移除多余的空行
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    def clean_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        # 替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # 移除多余空格
        filename = re.sub(r"\s+", " ", filename).strip()
        return filename

    def save_to_markdown(self, category: str, title: str, content: dict) -> Path | None:
        """保存内容到 Markdown 文件"""
        # 创建分类目录
        category_dir = self.output_dir / self.clean_filename(category)
        category_dir.mkdir(exist_ok=True)

        # 生成文件名
        safe_title = self.clean_filename(title)
        if not safe_title:
            safe_title = "untitled"
        filename = f"{safe_title}.md"
        filepath = category_dir / filename

        # 构建 Markdown 内容
        md_content = f"""# {content["title"] or title}

> 来源: [FRT Wiki]({content.get("url", "")})
> 分类: {category}
> 爬取时间: {time.strftime("%Y-%m-%d %H:%M:%S")}

---

{content["content"]}

---

*本文档由 FRT Wiki 爬虫自动生成*
"""

        if self.dry_run:
            print(f"    [试运行] 将保存: {filepath}")
            return filepath

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"    已保存: {filepath}")
        return filepath

    def crawl(self):
        """主爬取流程"""
        print("=" * 60)
        print("FRT Wiki 联盟规则爬虫")
        print(f"模式: {'增量更新' if self.incremental else '强制全量更新'}")
        if self.dry_run:
            print("注意: 试运行模式，不会保存任何文件")
        print("=" * 60)

        # 1. 获取起始页面
        print("\n[1/3] 正在分析规则结构...")
        soup = self.fetch_page(self.START_URL)
        if not soup:
            print("错误: 无法获取起始页面")
            return

        # 2. 提取侧边栏结构
        self.rules_structure = self.extract_sidebar_structure(soup)

        total_pages = sum(len(pages) for pages in self.rules_structure.values())
        self.stats["total"] = total_pages

        print(f"\n发现 {len(self.rules_structure)} 个分类，共 {total_pages} 个页面:")
        for category, pages in self.rules_structure.items():
            print(f"  - {category}: {len(pages)} 个页面")

        # 3. 爬取每个分类下的页面
        print("\n[2/3] 正在爬取各页面内容...")
        processed = 0

        for category, pages in self.rules_structure.items():
            print(f"\n  分类: {category}")

            for page_info in pages:
                processed += 1
                url = page_info["url"]
                title = page_info["title"]

                print(f"    [{processed}/{total_pages}] {title}")

                # 获取页面内容
                page_soup = self.fetch_page(url)
                if not page_soup:
                    continue

                # 提取内容
                content = self.extract_main_content(page_soup)
                content["url"] = url

                # 检查是否需要更新（使用正文原始HTML哈希）
                raw_html = content["raw_html"]
                should_update, reason = self.should_update(url, raw_html)
                content_text = content["content"]
                should_update, reason = self.should_update(url, content_text)

                if not should_update:
                    print(f"      跳过: {reason}")
                    self.stats["skipped"] += 1
                    continue

                print(f"      更新: {reason}")

                # 保存为 Markdown
                self.save_to_markdown(category, title, content)

                # 更新状态
                if not self.dry_run:
                    self.crawl_state[url] = {
                        "hash": self.get_page_hash(raw_html),
                        "updated_at": datetime.now().isoformat(),
                        "title": title,
                        "category": category,
                    }
                if not self.dry_run:
                    self.crawl_state[url] = {
                        "hash": self.get_page_hash(content_text),
                        "updated_at": datetime.now().isoformat(),
                        "title": title,
                        "category": category,
                    }

                if reason == "新页面":
                    self.stats["new"] += 1
                else:
                    self.stats["updated"] += 1

                # 礼貌延迟
                time.sleep(1)

        # 4. 生成索引文件
        print("\n[3/3] 生成索引文件...")
        self.generate_index()

        # 5. 保存状态
        self.save_state()

        # 6. 打印统计
        print("\n" + "=" * 60)
        print("爬取完成!")
        print(f"总计: {self.stats['total']} 个页面")
        print(f"  新增: {self.stats['new']} 个")
        print(f"  更新: {self.stats['updated']} 个")
        print(f"  跳过: {self.stats['skipped']} 个")
        print(f"  失败: {self.stats['failed']} 个")
        print(f"输出目录: {self.output_dir.absolute()}")
        if not self.dry_run:
            print(f"状态文件: {self.state_file}")
        print("=" * 60)

    def generate_index(self):
        """生成索引 README 文件"""
        readme_path = self.output_dir / "README.md"

        content = f"""# 凛冬联盟规则文档

> 来源: [FRT Wiki - 凛冬规则](https://wiki.winterco.org/zh/rules/start)
> 生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}
> 生成模式: {"增量更新" if self.incremental else "全量更新"}

## 目录结构

本文档包含以下分类的规则:

"""

        for category in sorted(self.rules_structure.keys()):
            content += f"\n### {category}\n\n"
            pages = self.rules_structure[category]
            for page in pages:
                safe_title = self.clean_filename(page["title"])
                content += f"- [{page['title']}](./{self.clean_filename(category)}/{safe_title}.md)\n"

        content += """

---

## 说明

- 本文档由自动爬虫程序生成
- 如需最新内容，请访问 [FRT Wiki](https://wiki.winterco.org/zh/rules/start)
- 如有疑问，请联系联盟管理

## 爬虫使用说明

```bash
# 增量更新（默认，只更新变更的页面）
python crawl_frt_rules.py

# 强制全量更新
python crawl_frt_rules.py --force

# 试运行（不保存文件，查看会发生什么）
python crawl_frt_rules.py --dry-run
```

"""

        if not self.dry_run:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"    已生成: {readme_path}")

            # 同时生成 JSON 格式的结构文件
            json_path = self.output_dir / "structure.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.rules_structure, f, ensure_ascii=False, indent=2)
            print(f"    已生成: {json_path}")
        else:
            print(f"    [试运行] 将生成: {readme_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="FRT Wiki 联盟规则爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python crawl_frt_rules.py              # 增量更新（默认）
  python crawl_frt_rules.py --force      # 强制全量更新
  python crawl_frt_rules.py --dry-run    # 试运行，不保存文件
        """,
    )

    parser.add_argument(
        "--force", "-f", action="store_true", help="强制全量更新，忽略缓存状态"
    )

    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="试运行模式，不保存任何文件"
    )

    parser.add_argument(
        "--output", "-o", default="frt_rules", help="输出目录（默认: frt_rules）"
    )

    args = parser.parse_args()

    crawler = FRTWikiCrawler(
        output_dir=args.output, incremental=not args.force, dry_run=args.dry_run
    )
    crawler.crawl()


if __name__ == "__main__":
    main()
