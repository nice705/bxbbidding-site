#!/usr/bin/env python3
"""
标讯宝 · 国家电网电商平台爬虫 (ecp.sgcc.com.cn)

通过 Cloudflare Pages 代理访问国家电网电子商务平台。
无需 Playwright，使用 requests + proxy_fetch 即可。

策略:
  1. 遍历多个采购类型路径（招标公告、中标结果、采购公告）
  2. 列表页通过代理获取 HTML，解析标题/链接/日期
  3. 详情页通过代理获取 HTML，解析结构化字段
  4. 增量合并去重

运行:
  python3 scripts/spider_sgcc.py
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
SOURCE_NAME = "国家电网采购"

# 多个基础 URL
BASE_URLS = [
    "https://ecp.sgcc.com.cn",
    "https://newbidding.sgcc.com.cn",
]

# REST API 风格的路径
REST_PATHS = [
    "/ecp2.0/portal/doc/list?type=1",     # 招标公告
    "/ecp2.0/portal/doc/list?type=2",     # 中标公告
    "/ecp2.0/portal/doc/list?type=3",     # 采购公告
    "/ecp2.0/portal/doc/list?type=4",     # 变更公告
]

MAX_PAGES = 5
MAX_DAYS_BACK = 14


def get_page_title(html: str) -> str:
    """从 HTML 提取 <title>"""
    m = re.search(r'<title>([^<]+)</title>', html)
    return m.group(1).strip() if m else ""


def check_connected(html: str) -> bool:
    """
    检查页面内容是否真正可用（非阻断/错误页）。
    """
    if not html or len(html) < 100:
        return False

    blocked_kws = ["403", "404", "禁止访问", "访问被拒绝", "Forbidden", "Not Found",
                   "Bad Gateway", "502", "503", "504", "页面访问提示", "暂停访问",
                   "WAF", "安全拦截", "访问受限"]
    text = re.sub(r'<[^>]+>', ' ', html)[:500]
    return not any(kw in text for kw in blocked_kws)


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

    # 匹配所有 <a> 链接
    link_pattern = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', re.IGNORECASE)
    for href, text in link_pattern.findall(html):
        text = text.strip()
        href = href.strip()

        if not href or not text or len(text) < 5:
            continue
        if href.startswith("javascript") or href == "#" or href == "":
            continue
        if href.endswith((".css", ".js", ".png", ".jpg", ".gif", ".ico")):
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
        context_text = _extract_link_context(html, href)
        date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', context_text)
        date_str = date_match.group(1).replace("/", "-") if date_match else ""

        results.append({
            "title": text,
            "url": full_url,
            "date": date_str,
        })

    # 去重（按标题 + URL 去重）
    seen_titles = set()
    unique_results = []
    for r in results:
        key = r["title"][:30] + r["url"][:60]
        if key not in seen_titles:
            seen_titles.add(key)
            unique_results.append(r)

    unique_results.sort(key=lambda r: r["date"], reverse=True)
    return unique_results


def _extract_link_context(html: str, href: str, window: int = 500) -> str:
    """提取链接周围的文本（用于日期查找）"""
    idx = html.find(href)
    if idx < 0:
        return ""
    start = max(0, idx - window)
    end = min(len(html), idx + window)
    return html[start:end]


def extract_detail_from_html(html: str, url: str) -> dict:
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

    # 提取文本
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) < 50:
        return None

    # 标题
    title = get_page_title(html)
    if not title:
        title_match = re.search(r'^(.{10,80})', text[:200])
        if title_match:
            title = title_match.group(1).strip()
    if not title:
        return None

    # 清理标题
    for suffix in ["_国家电网公司电子商务平台", " - 国家电网", " - SGCC"]:
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
    for pat in [r'(项目编号|招标编号|采购编号|分标编号)[：:]?\s*(\S+)',
                r'(GW-[A-Z0-9-]+)']:
        m = re.search(pat, text)
        if m:
            code = m.group(1) if len(m.groups()) == 1 else m.group(2).strip()[:50]
            break

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
    for pat in [r'(招标人|采购人|项目单位)[：:]?\s*([^\s]{2,40})',
                r'(国网|国家电网)\w{2,20}']:
        m = re.search(pat, text)
        if m:
            buyer = m.group(1) if len(m.groups()) == 1 else m.group(2).strip()
            if buyer:
                break

    # 截止日期
    deadline = ""
    m = re.search(r'(开标时间|投标截止|应答截止|文件递交截止)[^\\n]*?(\d{4}-\d{2}-\d{2})', text)
    if m:
        deadline = m.group(2)

    # 采购方式
    method = ""
    method_pats = [
        (r'公开招标', '公开招标'), (r'竞争性谈判', '竞争性谈判'),
        (r'竞争性磋商', '竞争性磋商'), (r'询价', '询价'),
        (r'单一来源', '单一来源'), (r'邀请招标', '邀请招标'),
        (r'中标|成交结果', '中标公告'), (r'招标公告', '招标公告'),
        (r'资格预审', '资格预审'), (r'竞价', '竞价'),
    ]
    for pat, name in method_pats:
        if re.search(pat, title) or re.search(pat, text[:1000]):
            method = name
            break

    # 行业
    industry = extract_industry(title)
    if not industry:
        if any(kw in (title + text[:500]) for kw in ["电力", "电网", "光伏", "风电", "能源", "配电", "输电", "变电站"]):
            industry = "能源电力"

    # 地区
    region = extract_region(title=title)
    if not region:
        m = re.search(r'(交货地点|项目地点|地点)[：:]?\s*([^\s]{2,20})', text)
        if m:
            region = m.group(2).strip()

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


def crawl_base_url(base_url: str) -> list:
    """
    爬取指定基础 URL 下的所有类型。

    参数:
        base_url: 基础 URL（如 https://ecp.sgcc.com.cn）
    """
    all_items = []
    print(f"\n--- 基础 URL: {base_url} ---")

    # 先测试连通性
    print(f"  🔗 测试连接: {base_url}")
    index_html = proxy_fetch_html(base_url)
    if not index_html or not check_connected(index_html):
        print(f"  ⚠ {base_url} 不可达，跳过")
        return all_items
    print(f"  ✅ 连通性检查通过")

    for path in REST_PATHS:
        path_label = path[:40]
        print(f"\n  类型: {path_label}")

        for pg in range(1, MAX_PAGES + 1):
            url = f"{base_url}{path}&pageNum={pg}&pageSize=20"
            print(f"  📄 page={pg}", end="", flush=True)

            html = proxy_fetch_html(url)
            if not html:
                print(" → 无法访问")
                break

            entries = extract_list_items(html, url)
            if not entries:
                print(f" → 0 条")
                break

            print(f" → {len(entries)} 条")

            cutoff = (datetime.now() - timedelta(days=MAX_DAYS_BACK)).strftime("%Y-%m-%d")

            for entry in entries:
                if entry["date"] and entry["date"] < cutoff:
                    continue

                print(f"  → {entry['title'][:50]}...", end=" ", flush=True)
                detail_html = proxy_fetch_html(entry["url"])
                if not detail_html:
                    print(f"❌ (无法访问)")
                    continue

                detail = extract_detail_from_html(detail_html, entry["url"])
                if detail:
                    all_items.append(detail)
                    print(f"✅")
                else:
                    print(f"❌ (解析失败)")

                random_delay(0.5, 1.5)

    return all_items


def main():
    print(f"\n{'='*50}")
    print(f"🔍 国家电网电商平台爬虫 (CF代理版) · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    all_new_items = []

    for base in BASE_URLS:
        try:
            items = crawl_base_url(base)
            all_new_items.extend(items)
            if items:
                break  # 如果有数据，不再尝试其他 base URL
        except Exception as e:
            print(f"  ⚠ {base} 失败: {e}")

    print(f"\n{'='*50}")
    print(f"📊 共爬取 {len(all_new_items)} 条新标讯")
    if all_new_items:
        append_bids(all_new_items, SOURCE_NAME)
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
