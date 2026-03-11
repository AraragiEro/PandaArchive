#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRT 联盟公司信息整合爬虫
从 FRT Wiki 和 Dotlan 抓取公司信息并整合

数据来源:
- https://wiki.winterco.org/zh/corps/start (中文信息、分类)
- https://evemaps.dotlan.net/alliance/Fraternity./corporations (成员数量、加入时间)

输出: frt_corp/公司总揽.md
"""

import re
import timehttps://evemaps.dotlan.net/alliance/Fraternity./corporations
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime

import requests
from bs4 import BeautifulSoup


class FRTCorpCrawler:
    """FRT 联盟公司信息爬虫"""

    WIKI_URL = "https://wiki.winterco.org/zh/corps/start"
    DOTLAN_URL = "https://evemaps.dotlan.net/alliance/Fraternity./corporations"

    def __init__(self, output_dir: str = "frt_corp"):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 存储公司信息
        self.wiki_corps = {}  # 从 Wiki 获取的中文信息
        self.dotlan_corps = {}  # 从 Dotlan 获取的详细信息

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        """获取页面内容"""
        try:
            print(f"  正在获取: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  错误: 无法获取 {url} - {e}")
            return None

    def parse_wiki_page(self, soup: BeautifulSoup) -> dict:
        """解析 Wiki 页面，提取公司信息"""
        corps = {}

        # 查找所有表格
        tables = soup.find_all("table", class_="inline")

        for table in tables:
            # 获取表格前的标题（分类）
            prev = table.find_previous(["h1", "h2", "h3"])
            category = "其他"
            if prev:
                category = prev.get_text(strip=True)
                # 清理标题
                category = re.sub(r"\s+", " ", category)

            # 解析表格行
            rows = table.find_all("tr")
            headers = []

            for i, row in enumerate(rows):
                if i == 0:
                    # 表头
                    headers = [
                        th.get_text(strip=True) for th in row.find_all(["th", "td"])
                    ]
                    continue

                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:
                    # 提取单元格数据
                    data = {}
                    for j, cell in enumerate(cells):
                        if j < len(headers):
                            key = headers[j]
                            value = cell.get_text(strip=True)
                            data[key] = value

                    # 确定公司名称（使用简称或全称）
                    ticker = data.get("简称", "")
                    name = data.get("全称", "")
                    cn_name = data.get("中文名", "")

                    if ticker or name:
                        key = ticker if ticker else name
                        corps[key] = {
                            "ticker": ticker,
                            "name": name,
                            "cn_name": cn_name,
                            "category": category,
                            "notes": data.get("特别备注", ""),
                            "source": "wiki",
                        }

        return corps

    def parse_dotlan_page(self, soup: BeautifulSoup) -> dict:
        """解析 Dotlan 页面，提取公司信息"""
        corps = {}

        # 查找公司表格
        table = soup.find("table", class_="tablelist sortable")
        if not table:
            print("  警告: 未找到 Dotlan 公司表格")
            return corps

        # 解析表格行
        rows = (
            table.find("tbody").find_all("tr")
            if table.find("tbody")
            else table.find_all("tr")[1:]
        )

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 5:
                # 提取数据
                logo_cell = cells[0]
                name_cell = cells[1]
                ticker_cell = cells[2]
                member_cell = cells[3]
                joined_cell = cells[4]

                # 获取公司名和 ticker
                name_link = name_cell.find("a")
                name = (
                    name_link.get_text(strip=True)
                    if name_link
                    else name_cell.get_text(strip=True)
                )
                ticker = ticker_cell.get_text(strip=True)
                members = member_cell.get_text(strip=True)
                joined = joined_cell.get_text(strip=True)

                # 提取公司 ID（从 logo URL）
                corp_id = None
                logo_img = logo_cell.find("img")
                if logo_img:
                    src = logo_img.get("src", "")
                    match = re.search(r"/Corporation/(\d+)_", src)
                    if match:
                        corp_id = match.group(1)

                if name and ticker:
                    corps[ticker] = {
                        "name": name,
                        "ticker": ticker,
                        "members": members,
                        "joined": joined,
                        "corp_id": corp_id,
                        "source": "dotlan",
                    }

        return corps

    def merge_corp_data(self) -> dict:
        """合并两个来源的数据"""
        merged = {}

        # 先处理所有 Dotlan 数据（包含所有公司）
        for ticker, data in self.dotlan_corps.items():
            merged[ticker] = {
                "ticker": ticker,
                "name": data["name"],
                "cn_name": "",
                "members": data["members"],
                "joined": data["joined"],
                "category": "其他",
                "notes": "",
                "corp_id": data.get("corp_id", ""),
            }

        # 合并 Wiki 数据（补充中文名和分类）
        for key, data in self.wiki_corps.items():
            ticker = data.get("ticker", "")

            if ticker and ticker in merged:
                # 更新已有公司信息
                merged[ticker]["cn_name"] = data.get("cn_name", "")
                merged[ticker]["category"] = data.get("category", "其他")
                merged[ticker]["notes"] = data.get("notes", "")
            else:
                # Wiki 中有但 Dotlan 中没有（可能是旧数据）
                merged[key] = {
                    "ticker": ticker,
                    "name": data.get("name", ""),
                    "cn_name": data.get("cn_name", ""),
                    "members": "-",
                    "joined": "-",
                    "category": data.get("category", "其他"),
                    "notes": data.get("notes", ""),
                    "corp_id": "",
                }

        return merged

    def generate_markdown(self, corps: dict) -> str:
        """生成 Markdown 格式的公司总揽"""
        # 按分类分组
        categories = {}
        for ticker, data in corps.items():
            category = data.get("category", "其他")
            if category not in categories:
                categories[category] = []
            categories[category].append(data)

        # 生成内容
        content = f"""# FRT 联盟公司总揽

> 数据来源:
> - [FRT Wiki 公司列表]({self.WIKI_URL})
> - [Dotlan 联盟公司]({self.DOTLAN_URL})
>
> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 联盟概况

- **总成员数**: {sum(int(c["members"]) for c in corps.values() if c["members"].isdigit())} 人
- **公司总数**: {len(corps)} 个

"""

        # 按分类输出
        category_order = [
            "FRTCN公司",
            "联盟直属公司",
            "FRTEN公司",
            "荣誉终身会员和附属公司",
            "其他",
        ]

        # 先输出已知分类
        for category in category_order:
            if category in categories:
                content += self._generate_category_section(
                    category, categories[category]
                )
                del categories[category]

        # 输出剩余分类
        for category, corps_list in sorted(categories.items()):
            content += self._generate_category_section(category, corps_list)

        # 添加完整列表
        content += """---

## 完整公司列表（按成员数排序）

| 简称 | 英文名称 | 中文名称 | 成员数 | 加入时间 | 备注 |
|------|----------|----------|--------|----------|------|
"""

        # 按成员数排序
        sorted_corps = sorted(
            corps.values(),
            key=lambda x: int(x["members"]) if x["members"].isdigit() else 0,
            reverse=True,
        )

        for data in sorted_corps:
            ticker = data.get("ticker", "")
            name = data.get("name", "")
            cn_name = data.get("cn_name", "")
            members = data.get("members", "-")
            joined = data.get("joined", "-")
            notes = data.get("notes", "")

            content += (
                f"| {ticker} | {name} | {cn_name} | {members} | {joined} | {notes} |\n"
            )

        content += """

---

*本文档由自动爬虫程序生成*
"""

        return content

    def _generate_category_section(self, category: str, corps_list: list) -> str:
        """生成分类章节"""
        # 按成员数排序
        sorted_list = sorted(
            corps_list,
            key=lambda x: int(x["members"]) if x["members"].isdigit() else 0,
            reverse=True,
        )

        content = f"""## {category}

| 简称 | 英文名称 | 中文名称 | 成员数 | 加入时间 | 备注 |
|------|----------|----------|--------|----------|------|
"""

        for data in sorted_list:
            ticker = data.get("ticker", "")
            name = data.get("name", "")
            cn_name = data.get("cn_name", "")
            members = data.get("members", "-")
            joined = data.get("joined", "-")
            notes = data.get("notes", "")

            content += (
                f"| {ticker} | {name} | {cn_name} | {members} | {joined} | {notes} |\n"
            )

        content += f"\n*共 {len(corps_list)} 个公司*\n\n"
        return content

    def crawl(self):
        """主爬取流程"""
        print("=" * 60)
        print("FRT 联盟公司信息爬虫")
        print("=" * 60)

        # 1. 获取 Wiki 数据
        print("\n[1/3] 正在获取 Wiki 公司信息...")
        wiki_soup = self.fetch_page(self.WIKI_URL)
        if wiki_soup:
            self.wiki_corps = self.parse_wiki_page(wiki_soup)
            print(f"  从 Wiki 获取到 {len(self.wiki_corps)} 个公司")
        else:
            print("  错误: 无法获取 Wiki 数据")

        # 2. 获取 Dotlan 数据
        print("\n[2/3] 正在获取 Dotlan 公司信息...")
        dotlan_soup = self.fetch_page(self.DOTLAN_URL)
        if dotlan_soup:
            self.dotlan_corps = self.parse_dotlan_page(dotlan_soup)
            print(f"  从 Dotlan 获取到 {len(self.dotlan_corps)} 个公司")
        else:
            print("  错误: 无法获取 Dotlan 数据")

        # 3. 合并数据并生成 Markdown
        print("\n[3/3] 正在合并数据并生成文档...")
        merged_corps = self.merge_corp_data()
        print(f"  合并后共 {len(merged_corps)} 个公司")

        markdown_content = self.generate_markdown(merged_corps)

        # 4. 保存文件
        output_file = self.output_dir / "公司总揽.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"\n  已保存: {output_file}")

        # 统计信息
        total_members = sum(
            int(c["members"]) for c in merged_corps.values() if c["members"].isdigit()
        )

        print("\n" + "=" * 60)
        print("爬取完成!")
        print(f"公司总数: {len(merged_corps)}")
        print(f"总成员数: {total_members}")
        print(f"输出文件: {output_file.absolute()}")
        print("=" * 60)


def main():
    """主函数"""
    crawler = FRTCorpCrawler(output_dir="frt_corp")
    crawler.crawl()


if __name__ == "__main__":
    main()
