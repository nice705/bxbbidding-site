#!/usr/bin/env python3
"""
标讯宝 · 军队采购网爬虫 (plap.cn)

通过 Cloudflare Pages 代理访问全军武器装备采购信息。
无需 Playwright，使用 requests + proxy_fetch 即可。

策略:
  1. 遍历多个采购类型路径
  2. 列表页通过代理获取 HTML，解析标题/链接/日期
  3. 详情页通过代理获取 HTML，解析结构化字段
  4. 增量合并去重

运行:
  python3 scripts/spider_plap.py
"""

import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.spider_base import (
    append_bids, extract_industry, extract_region, extract_budget,
    extract_code, extract_deadline, make_bid_item, md5, random_delay,
    is_good_content,
)
from scripts.spider_proxy import proxy_get, proxy_fetch_html

# ── 配置 ──
SOURCE_NAME = "军队采购网"
BASE_URL = "https://www.plap.cn"

# 多个尝试路径（不同采购类型）
PATHS = [
    "/cggg/",           # 采购公告总目录
    "/cgxx/",           # 采购信息
    "/zbgg/",           # 招标公告
    "/zfcg/",           # 政府采购
    "/gcjs/",           # 工程建设
    "/fwcg/",           # 服务采购
    "/cgxj/",           # 采购结果
    "/cgxx/zbgg/",      # 招标公告子目录
    "/cgxx/cgxj/",      # 采购结果子目录
]

MAX_PAGES = 5
MAX_DAYS_BACK = 14


def get_page_title(html: str) -> str:
    """从 HTML 提取 <title>"""
    m = re.search(r'<title>([^<]+)</title>', html)
    return m.group(1).strip() if m else ""


def scrape_list_page_html(html: str, base_url: str) -> list:
    """
    从列表页 HTML 提取标讯条目。

    返回:
        [(title, url, date_str), ...]
    """
    results = []
    seen_urls = set()

    if not html or len(html) < 200:
        return results

    # 匹配所有 <a> 标签
    # 策略: 提取有意义的链接
    link_pattern = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', re.IGNORECASE)
    for href, text in link_pattern.findall(html):
        text = text.strip()
        href = href.strip()

        # 过滤无效链接
        if not href or not text or len(text) < 5:
            continue
        if href.startswith("javascript") or href == "#" or href == "":
            continue
        if href.endswith("/") or "index" in href:
            continue
        if href.endswith((".css", ".js", ".png", ".jpg", ".gif", ".ico")):
            continue
        if "style" in href or "script" in href:
            continue

        # 构造完整 URL
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            full_url = base_url.rstrip("/") + href
        else:
            full_url = base_url.rstrip("/") + "/" + href

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # 提取日期 - 在 href 周围找日期
        # 先找行上下文
        lines = html.split("\n")
        context_lines = []
        for i, line in enumerate(lines):
            if href in line:
                # 取前后几行
                start = max(0, i - 3)
                end = min(len(lines), i + 4)
                context_lines = lines[start:end]
                break

        context_text = " ".join(context_lines)
        date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', context_text)
        date_str = date_match.group(1).replace("/", "-") if date_match else ""

        results.append({
            "title": text,
            "url": full_url,
            "date": date_str,
        })

    # 去除过短的标题
    results = [r for r in results if len(r["title"]) > 4]

    # 排序: 有日期的优先
    results.sort(key=lambda r: r["date"], reverse=True)

    return results


def scrape_list_page_item(html: str, base_url: str) -> list:
    """
    另一种列表提取策略: 查找 li > a 结构。
    适用于新闻列表/公告列表风格。
    """
    results = []
    seen_urls = set()

    if not html or len(html) < 200:
        return results

    # 查找 <li> 块，每块可能包含一个 <a> + 日期文本
    li_pattern = re.compile(r'<li[^>]*>(.*?)</li>', re.IGNORECASE | re.DOTALL)
    for li_match in li_pattern.finditer(html):
        li_content = li_match.group(1)

        # 提取链接
        a_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', li_content)
        if not a_match:
            continue

        href = a_match.group(1).strip()
        text = a_match.group(2).strip()

        if not href or not text or len(text) < 5:
            continue
        if href.startswith("javascript") or href == "#":
            continue

        # 构造完整 URL
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            full_url = base_url.rstrip("/") + href
        else:
            full_url = base_url.rstrip("/") + "/" + href

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # 从 li 内容提取日期
        date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', li_content)
        date_str = date_match.group(1).replace("/", "-") if date_match else ""

        results.append({
            "title": text,
            "url": full_url,
            "date": date_str,
        })

    results.sort(key=lambda r: r["date"], reverse=True)
    return results


def scrape_detail_html(html: str, url: str) -> dict:
    """
    从详情页 HTML 解析标讯字典。

    参数:
        html: 完整 HTML
        url: 详情页 URL

    返回:
        标讯字典，解析失败返回 None
    """
    if not html or len(html) < 200:
        return None

    # 提取文本（去掉 HTML 标签）
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) < 50:
        return None

    # 标题
    title = ""
    title_match = re.search(r'<title>([^<]+)</title>', html)
    if title_match:
        title = title_match.group(1).strip()
    else:
        # 尝试从内容提取
        title_match = re.search(r'^(.{10,80})', text[:200])
        if title_match:
            title = title_match.group(1).strip()
    if not title:
        return None

    # 清理标题: 去掉网站名后缀
    for suffix in ["_军队采购网", " - 军队采购网", " - 全军武器装备采购信息", " - 采购公告"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)]
            break

    # 日期
    date_str = ""
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text[:500])
    if date_match:
        date_str = date_match.group(1)

    # 项目编号
    code = ""
    m = re.search(r'(项目编号|采购编号|招标编号)[：:]?\s*(\S+)', text)
    if m:
        code = m.group(2).strip()[:50]

    # 预算
    budget = ""
    m = re.search(r'预算[：:]?\s*人民币\s*([0-9,.]+)\s*万元', text)
    if m:
        budget = m.group(1).replace(",", "")
    if not budget:
        m = re.search(r'预算[：:]?\s*([0-9,.]+)\s*万元', text)
        if m:
            budget = m.group(1).replace(",", "")

    # 采购人
    buyer = ""
    m = re.search(r'(采购人|招标人|采购方|需求方)[：:]?\s*([^\s]{2,40})', text)
    if m:
        buyer = m.group(2).strip()

    # 截止日期
    deadline = ""
    m = re.search(r'(开标时间|投标截止|提交投标文件截止)[^\\n]*?(\d{4}-\d{2}-\d{2})', text)
    if m:
        deadline = m.group(2)

    # 采购方式
    method = ""
    method_patterns = [
        (r'公开招标', '公开招标'), (r'竞争性谈判', '竞争性谈判'),
        (r'竞争性磋商', '竞争性磋商'), (r'询价', '询价'),
        (r'单一来源', '单一来源'), (r'邀请招标', '邀请招标'),
        (r'中标', '中标公告'), (r'招标公告', '招标公告'),
    ]
    for pat, name in method_patterns:
        if re.search(pat, title) or re.search(pat, text[:1000]):
            method = name
            break

    # 地区
    region = extract_region(title=title)
    if not region:
        m = re.search(r'(项目实施地点|交货地点|地点)[：:]?\s*([^\s]{2,20})', text)
        if m:
            region = m.group(2).strip()

    # 行业
    industry = extract_industry(title)
    if not industry:
        military_kws = ["军队", "武警", "边防", "人武", "军需", "国防", "军事"]
        for kw in military_kws:
            if kw in title or kw in text[:500]:
                industry = "安防消防"
                break

    return make_bid_item(
        title=title,
        source_url=url,
        source_name=SOURCE_NAME,
        content=text[:10000],
        industry=industry,
        region=region,
        method=method,
        budget=budget,
        date=date_str,
        deadline=deadline,
        buyer=buyer,
        code=code,
    )


def crawl_path(path: str) -> list:
    """
    爬取指定路径下的所有页面。

    参数:
        path: URL 路径（如 /cggg/）

    返回:
        标讯字典列表
    """
    items = []
    print(f"\n--- 路径: {path} ---")

    for pg in range(1, MAX_PAGES + 1):
        if pg == 1:
            url = f"{BASE_URL}{path}"
        else:
            url = f"{BASE_URL}{path}index_{pg}.html"

        # 通过代理获取列表页 HTML
        html = proxy_fetch_html(url)
        if not html:
            if pg == 1:
                print(f"  → {path} 无法访问")
            else:
                print(f"  → 第 {pg} 页无法访问，停止")
            break

        page_title = get_page_title(html)

        # 尝试两种方式提取列表
        entries = scrape_list_page_html(html, url)
        if not entries:
            entries = scrape_list_page_item(html, url)

        if not entries:
            if pg == 1:
                print(f"  → 未提取到条目")
            else:
                print(f"  → 第 {pg} 页无条目，停止")
            break

        print(f"  📄 page={pg}: 提取 {len(entries)} 条")

        cutoff = (datetime.now() - timedelta(days=MAX_DAYS_BACK)).strftime("%Y-%m-%d")

        for entry in entries:
            if entry["date"] and entry["date"] < cutoff:
                continue

            print(f"  → {entry['title'][:50]}...", end=" ", flush=True)

            # 通过代理获取详情页 HTML
            detail_html = proxy_fetch_html(entry["url"])
            if not detail_html:
                print(f"❌ (无法访问)")
                continue

            detail = scrape_detail_html(detail_html, entry["url"])
            if detail:
                items.append(detail)
                print(f"✅")
            else:
                print(f"❌ (解析失败)")

            random_delay(0.5, 1.5)

        # 如果第一页没条目，不再继续
        if pg == 1 and not any(
            e["date"] >= cutoff for e in entries if e["date"]
        ):
            print(f"  → 所有条目日期超出范围，停止")
            break

    return items


def main():
    print(f"\n{'='*50}")
    print(f"🔍 军队采购网爬虫 (CF代理版) · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    all_new_items = []

    for path in PATHS:
        try:
            items = crawl_path(path)
            all_new_items.extend(items)
        except Exception as e:
            print(f"  ⚠ 路径 {path} 失败: {e}")

    # 结果汇总
    print(f"\n{'='*50}")
    print(f"📊 共爬取 {len(all_new_items)} 条新标讯")
    if all_new_items:
        append_bids(all_new_items, SOURCE_NAME)
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
