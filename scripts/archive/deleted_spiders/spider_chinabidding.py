#!/usr/bin/env python3
"""
标讯宝 · 中国国际招标网爬虫 (chinabidding.com)

机电产品招标投标电子交易平台。
通过 Cloudflare Pages 代理访问。

运行:
  python3 scripts/spider_chinabidding.py
"""

import os
import sys
import re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.spider_base import (
    append_bids, extract_industry, extract_region, make_bid_item, random_delay
)
from scripts.spider_proxy import proxy_fetch_html

SOURCE_NAME = "中国国际招标网"
BASE = "https://www.chinabidding.com"
MAX_PAGES = 5
MAX_DAYS = 7

# 列表页源
SOURCES = [
    ("招标公告 (全部)", f"{BASE}/search/proj.htm?poClass=BidNotice&rangeType=1&pageNum={{page}}"),
    ("招标结果 (全部)", f"{BASE}/search/proj.htm?poClass=BidResult&rangeType=1&pageNum={{page}}"),
    ("招标首页", f"{BASE}/tender"),
]


def get_page_text(html: str) -> str:
    """从 HTML 提取纯文本"""
    text = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', text).strip()


def extract_list_items(html: str) -> list:
    """从列表页 HTML 提取标讯链接（支持 as-pager-item 嵌套结构）"""
    results = []
    seen_urls = set()

    if not html or len(html) < 200:
        return results

    # 查找 as-pager-item 链接（最新版 chinabidding 页面结构）
    link_pattern = re.compile(
        r'<a[^>]*class="as-pager-item"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL
    )
    for href, content in link_pattern.findall(html):
        href = href.strip()
        if not href or not content.strip():
            continue

        # 提取标题（从 title 属性）
        title_match = re.search(r'title="([^"]*)"', content)
        title = title_match.group(1).strip() if title_match else ""

        # 也尝试从 span.txt 文本提取
        if not title or len(title) < 5:
            txt_match = re.search(r'class="txt"[^>]*>([^<]+)', content)
            title = txt_match.group(1).strip() if txt_match else ""

        if not title or len(title) < 5:
            continue

        # 构造完整URL
        if href.startswith("http"):
            full_url = href
        else:
            full_url = BASE.rstrip("/") + ("/" if not href.startswith("/") else "") + href

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # 提取日期
        date_match = re.search(r'发布时间[：:]?(\d{4}-\d{2}-\d{2})', content)
        date_str = date_match.group(1) if date_match else ""

        results.append({"title": title, "url": full_url, "date": date_str})

    # 如果没找到 as-pager-item，回退到旧版解析（查找 bidDetail 链接）
    if not results:
        link_pattern2 = re.compile(
            r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', re.IGNORECASE
        )
        for href, text in link_pattern2.findall(html):
            text = text.strip()
            href = href.strip()
            if not href or not text or len(text) < 5:
                continue
            if href in ("#", "", "javascript:void(0)") or href.startswith("javascript"):
                continue
            if "bidDetail" not in href:
                continue
            if href.startswith("http"):
                full_url = href
            else:
                full_url = BASE.rstrip("/") + ("/" if not href.startswith("/") else "") + href
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            idx = html.find(href)
            ctx = html[max(0, idx - 300):min(len(html), idx + 300)]
            ctx_text = get_page_text(ctx)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', ctx_text)
            date_str = date_match.group(1) if date_match else ""
            results.append({"title": text, "url": full_url, "date": date_str})

    # 去重
    seen_keys = set()
    unique = []
    for r in results:
        key = r["title"][:30] + r["url"][:60]
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(r)

    return unique


def extract_detail(html: str, url: str) -> dict:
    """从详情页 HTML 解析标讯字典"""
    if not html or len(html) < 200:
        return None

    text = get_page_text(html)
    if len(text) < 50:
        return None

    # 标题
    title_match = re.search(r'<title>([^<]+)</title>', html)
    title = title_match.group(1).strip() if title_match else ""
    if not title:
        title_match = re.search(r'^(.{10,80})', text[:200])
        if title_match:
            title = title_match.group(1).strip()
    if not title:
        return None

    # 日期
    date_str = (m := re.search(r'(\d{4}-\d{2}-\d{2})', text[:500])) and m.group(1) or ""

    # 项目编号
    code = (m := re.search(r'招标项目编号[：:]?\s*(\S+)', text)) and m.group(1).strip() or ""

    # 预算
    budget = ""
    for p in [r'预算[：:]?\s*人民币\s*([0-9,.]+)\s*万元', r'预算[：:]?\s*([0-9,.]+)\s*万元']:
        if (m := re.search(p, text)):
            budget = m.group(1).replace(",", "")
            break

    # 采购人
    buyer = (m := re.search(r'招标人[：:]?\s*(.+?)(?:\n|$)', text)) and m.group(1).strip() or ""

    # 截止日期
    deadline = ""
    for p in [r'开标时间[：:]?\s*(\d{4}-\d{2}-\d{2})', r'评标公示截止时间[：:]?\s*(\d{4}-\d{2}-\d{2})']:
        if (m := re.search(p, text)):
            deadline = m.group(1)
            break

    # 采购方式
    method = ""
    if "招标公告" in title:
        method = "公开招标"
    elif "评标结果" in title or "招标结果" in title:
        method = "评标结果公示"
    elif "中标结果" in title:
        method = "中标公告"

    # 地域
    region = extract_region(title=title)
    if not region:
        region = (m := re.search(r'项目实施地点[：:]?\s*(.+?)(?:\n|$)', text)) and m.group(1).strip() or ""

    return make_bid_item(
        title=title, source_url=url, source_name=SOURCE_NAME, content=text[:8000],
        industry=extract_industry(title), region=region, method=method,
        budget=budget, date=date_str, deadline=deadline, buyer=buyer, code=code,
    )


def main():
    print(f"\n{'='*50}")
    print(f"🔍 {SOURCE_NAME} (CF代理版) · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    all_new = []
    cutoff = (datetime.now() - timedelta(days=MAX_DAYS)).strftime("%Y-%m-%d")

    for label, url_tpl in SOURCES:
        print(f"\n--- {label} ---")
        for pg in range(1, MAX_PAGES + 1):
            url = url_tpl.format(page=pg) if "{page}" in url_tpl else url_tpl
            if pg > 1 and "{page}" not in url_tpl:
                break

            print(f"  📄 p{pg}...", end=" ", flush=True)
            html = proxy_fetch_html(url)
            if not html:
                print("→ 无法访问")
                break

            items = extract_list_items(html)
            if not items:
                print("→ 0 条")
                break

            print(f"→ {len(items)} 条")

            for item in items:
                if item["date"] and item["date"] < cutoff:
                    continue

                print(f"  → {item['title'][:50]}...", end=" ", flush=True)
                detail_html = proxy_fetch_html(item["url"])
                if not detail_html:
                    print(f"❌")
                    continue

                detail = extract_detail(detail_html, item["url"])
                if detail:
                    all_new.append(detail)
                    print(f"✅")
                else:
                    print(f"❌ (解析失败)")

                random_delay(0.5, 1.0)

    print(f"\n📊 共爬取 {len(all_new)} 条")
    if all_new:
        append_bids(all_new, SOURCE_NAME)
    print("✅ 完成")


if __name__ == "__main__":
    main()
