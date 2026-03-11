#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRT Wiki 联盟规则爬虫
爬取 https://wiki.winterco.org/zh/rules/start 及其所有子页面
并将内容分类保存为 Markdown 文件
"""

import os
import re
import time
import json
from urllib.parse import urljoin, urlparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup


class FRTWikiCrawler:
    """FRT Wiki 爬虫类"""

    BASE_URL = "https://wiki.winterco.org"
    START_URL = "https://wiki.winterco.org/zh/rules/start"

    def __init__(self, output_dir: str = "rules_output"):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 存储所有规则页面信息
        self.rules_structure = {}

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        """获取页面内容并解析"""
        try:
            print(f"  正在获取: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  错误: 无法获取 {url} - {e}")
            return None

    def extract_sidebar_structure(self, soup: BeautifulSoup) -> dict:
        """从侧边栏提取规则分类结构"""
        structure = {}

        # 查找侧边栏中的所有面板
        panels = soup.find_all("div", class_=lambda x: x and "panel" in x and "panel-default" in x)

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
        content_data = {"title": "", "content": "", "headings": []}

        # 提取标题
        title_elem = soup.find("h1", class_="page-header")
        if title_elem:
            content_data["title"] = title_elem.get_text(strip=True)

        # 提取主要内容区域
        content_div = soup.find("div", {"itemprop": "articleBody"})
        if not content_div:
            content_div = soup.find("div", id="dokuwiki__content")

        if content_div:
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

    def save_to_markdown(self, category: str, title: str, content: dict):
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

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"    已保存: {filepath}")
        return filepath

    def crawl(self):
        """主爬取流程"""
        print("=" * 60)
        print("FRT Wiki 联盟规则爬虫")
        print("=" * 60)

        # 1. 获取起始页面
        print("\n[1/3] 正在分析规则结构...")
        soup = self.fetch_page(self.START_URL)
        if not soup:
            print("错误: 无法获取起始页面")
            return

        # 2. 提取侧边栏结构
        self.rules_structure = self.extract_sidebar_structure(soup)

        print(f"\n发现 {len(self.rules_structure)} 个分类:")
        for category, pages in self.rules_structure.items():
            print(f"  - {category}: {len(pages)} 个页面")

        # 3. 爬取每个分类下的页面
        print("\n[2/3] 正在爬取各页面内容...")
        total_pages = sum(len(pages) for pages in self.rules_structure.values())
        processed = 0

        for category, pages in self.rules_structure.items():
            print(f"\n  分类: {category}")

            for page_info in pages:
                processed += 1
                print(f"    [{processed}/{total_pages}] {page_info['title']}")

                # 获取页面内容
                page_soup = self.fetch_page(page_info["url"])
                if page_soup:
                    content = self.extract_main_content(page_soup)
                    content["url"] = page_info["url"]

                    # 保存为 Markdown
                    self.save_to_markdown(category, page_info["title"], content)

                    # 礼貌延迟
                    time.sleep(1)

        # 4. 生成索引文件
        print("\n[3/3] 生成索引文件...")
        self.generate_index()

        print("\n" + "=" * 60)
        print("爬取完成!")
        print(f"输出目录: {self.output_dir.absolute()}")
        print("=" * 60)

    def generate_index(self):
        """生成索引 README 文件"""
        readme_path = self.output_dir / "README.md"

        content = f"""# 凛冬联盟规则文档

> 来源: [FRT Wiki - 凛冬规则](https://wiki.winterco.org/zh/rules/start)
> 生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}

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

"""

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"    已生成: {readme_path}")

        # 同时生成 JSON 格式的结构文件
        json_path = self.output_dir / "structure.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.rules_structure, f, ensure_ascii=False, indent=2)
        print(f"    已生成: {json_path}")


def main():
    """主函数"""
    crawler = FRTWikiCrawler(output_dir="frt_rules")
    crawler.crawl()


if __name__ == "__main__":
    main()
