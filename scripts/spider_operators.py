#!/usr/bin/env python3
"""
标讯宝 · 三大运营商 + 央企采购平台爬虫（CF代理版）

覆盖大型央企采购平台：
  - 中国移动采购与招标网 (b2b.10086.cn)
  - 中国联通采购与招标网 (www.chinaunicombidding.cn)
  - 中国电信阳光采购网 (caigou.chinatelecom.com.cn)
  - 中国石油招标投标网 (www.cnpcbidding.com)
  - 中国石化电子招标投标交易平台 (bidding.sinopec.com)
  - 中国海洋石油总公司采办业务管理系统 (buy.cnooc.com.cn)

通过 Cloudflare Pages 代理访问被阻断站点。
无需 Playwright，使用 requests + proxy_fetch 即可。

运行:
  python3 scripts/spider_operators.py
  或指定平台:
  python3 scripts/spider_operators.py --platforms cmcc,cnpc,sinopec
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.spider_base import (
    append_bids, extract_industry, extract_region, extract_budget,
    extract_code, extract_deadline, make_bid_item, md5, random_delay,
)
from scripts.spider_proxy import proxy_fetch_html

# ── 平台配置 ──
# (code, name, source_name, base_url, paths, industry_hint, region_hint)
PLATFORMS = [
    {
        "code": "cmcc",
        "name": "中国移动采购与招标网",
        "source_name": "中国移动",
        "base_url": "https://b2b.10086.cn",
        "paths": [
            "/b2b/main/viewNotice.html?noticeType=1",   # 招标公告
            "/b2b/main/viewNotice.html?noticeType=2",   # 中标结果
            "/b2b/main/viewNotice.html?noticeType=3",   # 采购公告
        ],
        "industry_hint": "IT信息化",
        "region_hint": "",
    },
    {
        "code": "cucc",
        "name": "中国联通采购与招标网",
        "source_name": "中国联通",
        "base_url": "https://www.chinaunicombidding.cn",
        "paths": ["/", "/jyxx/", "/zbgg/", "/cgxx/"],
        "industry_hint": "IT信息化",
        "region_hint": "",
    },
    {
        "code": "ctcc",
        "name": "中国电信阳光采购网",
        "source_name": "中国电信",
        "base_url": "https://caigou.chinatelecom.com.cn",
        "paths": ["/", "/jyxx/", "/zbgg/", "/cgxx/"],
        "industry_hint": "IT信息化",
        "region_hint": "",
    },
    {
        "code": "cnpc",
        "name": "中国石油招标投标网",
        "source_name": "中国石油",
        "base_url": "https://www.cnpcbidding.com",
        "paths": ["/", "/zbgg/", "/cgxx/", "/jyxx/"],
        "industry_hint": "能源电力",
        "region_hint": "",
    },
    {
        "code": "sinopec",
        "name": "中国石化电子招标投标交易平台",
        "source_name": "中国石化",
        "base_url": "https://bidding.sinopec.com",
        "paths": ["/", "/zbgg/", "/cgxx/", "/jyxx/"],
        "industry_hint": "能源电力",
        "region_hint": "",
    },
    {
        "code": "cnooc",
        "name": "中国海油采办业务管理系统",
        "source_name": "中国海油",
        "base_url": "https://buy.cnooc.com.cn",
        "paths": ["/", "/zbgg/", "/cgxx/", "/jyxx/"],
        "industry_hint": "能源电力",
        "region_hint": "",
    },
]

MAX_DAYS_BACK = 7


def get_page_text(html: str) -> str:
    """从 HTML 提取纯文本"""
    text = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', text).strip()


def is_blocked_page(text: str) -> bool:
    """检查页面内容是否被阻断"""
    blocked = ["403", "404", "禁止访问", "访问被拒绝", "Forbidden", "Not Found",
               "Bad Gateway", "502", "503", "504", "页面访问提示", "暂停访问",
               "WAF", "安全拦截", "访问受限", "验证", "安全检查"]
    return any(kw in text for kw in blocked)


def extract_list_items(html: str, base_url: str) -> list:
    """
    从列表页 HTML 提取标讯条目。

    返回:
        [{title, url, date}, ...]
    """
    results = []
    seen_urls = set()

    if not html or len(html) < 200:
        return results

    # 查找所有 <a> 链接
    link_pattern = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', re.IGNORECASE)
    for href, text in link_pattern.findall(html):
        text = text.strip()
        href = href.strip()

        if not href or not text or len(text) < 5:
            continue
        if href.startswith("javascript") or href in ("#", "", "javascript:void(0)"):
            continue
        if href.endswith((".css", ".js", ".png", ".jpg", ".gif", ".ico", ".svg")):
            continue
        if "index" in href or "style" in href:
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

        # 从周围上下文提取日期
        idx = html.find(href)
        ctx_start = max(0, idx - 300)
        ctx_end = min(len(html), idx + 300)
        context_text = get_page_text(html[ctx_start:ctx_end])

        date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', context_text)
        date_str = date_match.group(1).replace("/", "-") if date_match else ""

        results.append({
            "title": text,
            "url": full_url,
            "date": date_str,
        })

    # 去重
    seen_keys = set()
    unique = []
    for r in results:
        key = r["title"][:30] + r["url"][:60]
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(r)

    unique.sort(key=lambda r: r["date"], reverse=True)
    return unique


def extract_detail_from_html(html: str, url: str, industry_hint: str,
                              region_hint: str, source_name: str) -> dict:
    """
    从详情页 HTML 解析标讯字典。
    """
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
    date_str = ""
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text[:500])
    if date_match:
        date_str = date_match.group(1)

    # 项目编号
    code = ""
    for pat in [r'(项目编号|招标编号|采购编号)[：:]?\s*(\S+)',
                r'编号[：:]?\s*([A-Z0-9\-_]{8,})']:
        m = re.search(pat, text)
        if m:
            code = (m.group(2) if len(m.groups()) > 1 else m.group(1)).strip()[:50]
            break

    # 预算
    budget = ""
    m = re.search(r'预算[：:]?\s*([0-9,.]+)\s*万元', text)
    if m:
        budget = m.group(1).replace(",", "")
    else:
        m = re.search(r'金额[：:]?\s*([0-9,.]+)\s*万元', text)
        if m:
            budget = m.group(1).replace(",", "")

    # 采购人
    buyer = ""
    for pat in [r'(招标人|采购人|采购单位|业主)[：:]?\s*([^\s]{2,40})',
                r'(项目单位|需求方)[：:]?\s*([^\s]{2,40})']:
        m = re.search(pat, text)
        if m:
            buyer = m.group(2).strip()
            if buyer:
                break

    # 截止日期
    deadline = ""
    m = re.search(r'(开标时间|投标截止|应答截止|文件递交截止|报名截止)[^\\n]*?(\d{4}-\d{2}-\d{2})', text)
    if m:
        deadline = m.group(2)

    # 采购方式
    method = ""
    method_pats = [
        (r'公开招标', '公开招标'), (r'竞争性谈判', '竞争性谈判'),
        (r'竞争性磋商', '竞争性磋商'), (r'询价', '询价'),
        (r'单一来源', '单一来源'), (r'邀请招标', '邀请招标'),
        (r'中标结果|中标公告|成交公告', '中标公告'),
        (r'招标公告', '招标公告'), (r'资格预审', '资格预审'),
        (r'竞价', '竞价'), (r'比选', '比选'),
    ]
    for pat, name in method_pats:
        if re.search(pat, title) or re.search(pat, text[:1000]):
            method = name
            break

    # 行业
    industry = ""
    if industry_hint:
        auto_industry = extract_industry(title)
        if auto_industry:
            industry = auto_industry
        else:
            industry = industry_hint
    else:
        industry = extract_industry(title)
        if not industry:
            industry = extract_industry(title + " " + text[:500])

    # 地区
    region = region_hint if region_hint else extract_region(title=title)
    if not region:
        m = re.search(r'(项目实施地点|交货地点|地点|所在地区)[：:]?\s*([^\s]{2,20})', text)
        if m:
            region = m.group(2).strip()

    return make_bid_item(
        title=title,
        source_url=url,
        source_name=source_name,
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


def crawl_platform(platform: dict) -> list:
    """爬取单个平台"""
    base_url = platform["base_url"]
    plat_name = platform["name"]
    source_name = platform["source_name"]
    industry_hint = platform["industry_hint"]
    region_hint = platform["region_hint"]
    items = []

    print(f"\n{'='*50}")
    print(f"📡 {plat_name} ({base_url})")
    print(f"{'='*50}")

    # 测试连通性
    print(f"  🔗 测试连接...", end=" ", flush=True)
    index_html = proxy_fetch_html(base_url, timeout=20)
    if not index_html or is_blocked_page(index_html[:500]):
        print(f"❌ 不可达或被阻断")
        return items
    print(f"✅ ({len(index_html)} chars)")

    # 尝试各路径
    for path in platform["paths"]:
        full_url = f"{base_url}{path}"
        path_label = path[:50]
        print(f"\n  路径: {path_label}")

        html = proxy_fetch_html(full_url, timeout=20)
        if not html:
            print(f"  → 无法访问")
            continue

        entries = extract_list_items(html, full_url)
        if not entries:
            print(f"  → 无条目")
            continue

        print(f"  📄 {len(entries)} 条")

        cutoff = (datetime.now() - timedelta(days=MAX_DAYS_BACK)).strftime("%Y-%m-%d")

        for entry in entries:
            if entry["date"] and entry["date"] < cutoff:
                continue

            print(f"  → {entry['title'][:50]}...", end=" ", flush=True)
            detail_html = proxy_fetch_html(entry["url"], timeout=20)
            if not detail_html:
                print(f"❌ (无法访问)")
                continue

            detail = extract_detail_from_html(detail_html, entry["url"],
                                              industry_hint, region_hint, source_name)
            if detail:
                items.append(detail)
                print(f"✅")
            else:
                print(f"❌ (解析失败)")

            random_delay(0.5, 1.5)

    return items


def main():
    parser = argparse.ArgumentParser(description="运营商/央企采购平台爬虫")
    parser.add_argument("--platforms", type=str, default="",
                        help="指定平台代码（逗号分隔），如 cmcc,cnpc,sinopec")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"🔍 运营商/央企采购平台爬虫 (CF代理版) · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    # 筛选平台
    if args.platforms:
        selected = set(args.platforms.split(","))
        platforms = [p for p in PLATFORMS if p["code"] in selected]
        print(f"📋 指定平台: {', '.join(p['code'] for p in platforms)} ({len(platforms)}个)")
    else:
        platforms = PLATFORMS
        print(f"📋 全部 {len(platforms)} 个平台")

    all_new_items = []
    failed_platforms = []

    for plat in platforms:
        try:
            items = crawl_platform(plat)
            all_new_items.extend(items)
            if not items:
                failed_platforms.append(plat["code"])
                print(f"\n  ⚠ {plat['name']} 无数据")
        except Exception as e:
            print(f"\n  ⚠ {plat['name']} 失败: {e}")
            failed_platforms.append(plat["code"])
        random_delay(1.0, 2.0)

    # 结果汇总
    successful = [p["code"] for p in platforms if p["code"] not in failed_platforms]
    print(f"\n{'='*50}")
    print(f"✅ 成功平台 ({len(successful)}): {', '.join(successful) if successful else '无'}")
    print(f"⚠️ 失败平台 ({len(failed_platforms)}): {', '.join(failed_platforms) if failed_platforms else '无'}")
    print(f"📊 共爬取 {len(all_new_items)} 条新标讯")

    if all_new_items:
        append_bids(all_new_items, "央企采购平台")

    print(f"{'='*50}")


if __name__ == "__main__":
    main()
