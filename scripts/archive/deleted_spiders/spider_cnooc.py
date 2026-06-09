#!/usr/bin/env python3
"""标讯宝 · 中国海油采办业务管理系统爬虫 (Playwright版)"""

import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from scripts.spider_base import append_bids, extract_industry, extract_region, make_bid_item, random_delay
from scripts.pw_fetch import pw_fetch_html, pw_close

SOURCE_NAME = "中国海油"
BASE = "https://buy.cnooc.com.cn"
INDEX_URL = f"{BASE}/cbjyweb/index.html"
MAX_ITEMS = 50
MAX_DAYS = 3

def extract_list_items(html: str) -> list:
    """从首页提取标讯链接"""
    results = []
    seen = set()
    pattern = re.compile(r'<a[^>]*href="([^"]*zhy\.html)"[^>]*>(.*?)</a>', re.DOTALL)
    for href, content in pattern.findall(html):
        text = re.sub(r'<[^>]+>', '', content).strip()
        if not text or len(text) < 10:
            continue
        if text in seen:
            continue
        seen.add(text)
        full_url = BASE + href if href.startswith("/") else href
        results.append({"title": text, "url": full_url, "date": ""})
    return results

def extract_detail(html: str, url: str) -> dict:
    """从详情页提取标讯字段"""
    if not html or len(html) < 200:
        return None

    # 标题
    title_m = re.search(r'<title>([^<]+)</title>', html)
    title = title_m.group(1).strip() if title_m else ""

    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()

    # 招标编号
    code = ""
    for p in [r'标段（包）编号[：:]\s*(\S+)', r'项目编号[：:]\s*(\S+)']:
        m = re.search(p, text)
        if m:
            code = m.group(1).strip()
            break

    # 发标日期
    date_str = ""
    for p in [r'发标日期[：:]\s*(\d{4}年\d{2}月\d{2}日)', r'(\d{4}-\d{2}-\d{2})']:
        m = re.search(p, text)
        if m:
            date_str = m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            break

    # 预算
    budget = ""
    for p in [r'预算[：:]\s*([0-9,.]+)\s*万元', r'金额[：:]\s*¥?\s*([0-9,.]+)\s*万']:
        m = re.search(p, text)
        if m:
            budget = m.group(1).replace(",", "")
            break

    # 采购人
    buyer = ""
    for p in [r'招标人[：:]\s*(.+?)(?:\n|$)', r'采购人[：:]\s*(.+?)(?:\n|$)']:
        m = re.search(p, text)
        if m:
            buyer = m.group(1).strip()
            break

    # 截止日期
    deadline = ""
    for p in [r'投标截止时间[：:]\s*(\d{4}年\d{2}月\d{2}日)', r'开标时间[：:]\s*(\d{4}年\d{2}月\d{2}日)']:
        m = re.search(p, text)
        if m:
            deadline = m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            break

    # 采购方式
    method = ""
    if '招标公告' in text[:500]:
        method = '公开招标'
    elif '中标' in text[:500]:
        method = '中标公告'
    elif '变更' in text[:500]:
        method = '变更公告'

    return make_bid_item(
        title=title or (re.search(r'^(.{10,60})', text) and re.search(r'^(.{10,60})', text).group(1)) or "",
        source_url=url, source_name=SOURCE_NAME, content=text[:10000],
        industry=extract_industry(title or ""), region="",
        method=method, budget=budget, date=date_str,
        deadline=deadline, buyer=buyer, code=code,
    )

def main():
    print(f"\n{'='*50}")
    print(f"🔍 {SOURCE_NAME} (Playwright版) · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    html = pw_fetch_html(INDEX_URL, timeout=20)
    if not html:
        print("  ❌ 首页获取失败")
        pw_close()
        return

    items = extract_list_items(html)
    print(f"  首页发现 {len(items)} 条标讯")

    if not items:
        pw_close()
        return

    all_new = []
    for item in items[:MAX_ITEMS]:
        print(f"  → {item['title'][:50]}...", end=" ", flush=True)
        detail_html = pw_fetch_html(item["url"], timeout=20)
        if not detail_html:
            print("❌")
            continue

        detail = extract_detail(detail_html, item["url"])
        if detail:
            all_new.append(detail)
            print("✅")
        else:
            print("❌ (解析失败)")

        random_delay(1, 2)

    print(f"\n📊 共爬取 {len(all_new)} 条")
    if all_new:
        append_bids(all_new, SOURCE_NAME)

    print("✅ 完成")

if __name__ == "__main__":
    main()
