#!/usr/bin/env python3
"""
标讯宝 · 省级公共资源交易中心爬虫（CF代理版）

覆盖全部 31 个省/自治区/直辖市的公共资源交易平台。
通过 Cloudflare Pages 代理访问被阻断站点。

策略:
  1. 每个省份站点通过代理获取 HTML
  2. 列表页提取采购公告标题/链接/日期
  3. 详情页解析结构化字段
  4. 增量合并去重

运行:
  python3 scripts/spider_provinces.py
  或指定省份:
  python3 scripts/spider_provinces.py --provinces zj,gd,sd
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

# ── 全国 31 个省/自治区/直辖市公共资源交易平台 ──
# (code, name, base_url, region_hint)
PROVINCE_SITES = [
    # ── 直辖市 ──
    {
        "code": "bj",
        "name": "北京市公共资源交易中心",
        "base_url": "https://ggzy.bj.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "北京",
    },
    {
        "code": "sh",
        "name": "上海市公共资源交易中心",
        "base_url": "https://ggzy.sh.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "上海",
    },
    {
        "code": "tj",
        "name": "天津市公共资源交易中心",
        "base_url": "https://ggzy.tj.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "天津",
    },
    {
        "code": "cq",
        "name": "重庆市公共资源交易中心",
        "base_url": "https://ggzy.cq.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "重庆",
    },
    # ── 华东地区 ──
    {
        "code": "zj",
        "name": "浙江省公共资源交易中心",
        "base_url": "https://ggzy.zj.gov.cn",
        "paths": ["/zhejiangnew/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "浙江",
        "render_type": "portal",  # 门户站点,数据需从下级目录抓取
    },
    {
        "code": "gd",
        "name": "广东省公共资源交易中心",
        "base_url": "https://ggzy.gd.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "广东",
    },
    {
        "code": "sd",
        "name": "山东省公共资源交易中心",
        "base_url": "https://ggzy.shandong.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "山东",
    },
    {
        "code": "js",
        "name": "江苏省公共资源交易中心",
        "base_url": "https://ggzy.jszwfw.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "江苏",
    },
    {
        "code": "fj",
        "name": "福建省公共资源交易中心",
        "base_url": "https://ggzy.fujian.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "福建",
    },
    {
        "code": "ah",
        "name": "安徽省公共资源交易中心",
        "base_url": "https://ggzy.ah.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "安徽",
    },
    {
        "code": "jx",
        "name": "江西省公共资源交易中心",
        "base_url": "https://ggzy.jiangxi.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "江西",
    },
    # ── 华北地区 ──
    {
        "code": "hb",
        "name": "河北省公共资源交易中心",
        "base_url": "https://ggzy.hebei.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "河北",
    },
    {
        "code": "shanxi",
        "name": "山西省公共资源交易中心",
        "base_url": "https://ggzy.shanxi.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "山西",
    },
    {
        "code": "nm",
        "name": "内蒙古自治区公共资源交易中心",
        "base_url": "https://ggzy.nmg.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "内蒙古",
    },
    # ── 华中地区 ──
    {
        "code": "hubei",
        "name": "湖北省公共资源交易中心",
        "base_url": "https://ggzy.hubei.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "湖北",
    },
    {
        "code": "henan",
        "name": "河南省公共资源交易中心",
        "base_url": "https://ggzy.henan.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "河南",
    },
    {
        "code": "hunan",
        "name": "湖南省公共资源交易中心",
        "base_url": "https://ggzy.hunan.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "湖南",
    },
    # ── 东北地区 ──
    {
        "code": "ln",
        "name": "辽宁省公共资源交易中心",
        "base_url": "https://ggzy.ln.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "辽宁",
    },
    {
        "code": "jl",
        "name": "吉林省公共资源交易中心",
        "base_url": "https://ggzy.jl.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "吉林",
    },
    {
        "code": "hlj",
        "name": "黑龙江省公共资源交易中心",
        "base_url": "https://ggzy.hlj.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "黑龙江",
    },
    # ── 西南地区 ──
    {
        "code": "sc",
        "name": "四川省公共资源交易中心",
        "base_url": "https://ggzy.sichuan.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/", "/jyxx/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "四川",
    },
    {
        "code": "gz",
        "name": "贵州省公共资源交易中心",
        "base_url": "https://ggzy.guizhou.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "贵州",
    },
    {
        "code": "yn",
        "name": "云南省公共资源交易中心",
        "base_url": "https://ggzy.yunnan.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "云南",
    },
    {
        "code": "xz",
        "name": "西藏自治区公共资源交易中心",
        "base_url": "https://ggzy.xizang.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "西藏",
    },
    # ── 西北地区 ──
    {
        "code": "shaanxi",
        "name": "陕西省公共资源交易中心",
        "base_url": "https://ggzy.shaanxi.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "陕西",
    },
    {
        "code": "gs",
        "name": "甘肃省公共资源交易中心",
        "base_url": "https://ggzy.gansu.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "甘肃",
    },
    {
        "code": "qh",
        "name": "青海省公共资源交易中心",
        "base_url": "https://ggzy.qinghai.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "青海",
    },
    {
        "code": "nx",
        "name": "宁夏回族自治区公共资源交易中心",
        "base_url": "https://ggzy.ningxia.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "宁夏",
    },
    {
        "code": "xj",
        "name": "新疆维吾尔自治区公共资源交易中心",
        "base_url": "https://ggzy.xinjiang.gov.cn",
        "paths": ["/xinjiangggzy/jyxx/001001/001001001/tradeInfo_new.html", "/xinjiangggzy/jyxx/001001/001001002/tradeInfo_new.html", "/xinjiangggzy/jyxx/tradeInfo_new.html"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "新疆",
        "render_type": "list",
    },
    # ── 华南地区 ──
    {
        "code": "gx",
        "name": "广西壮族自治区公共资源交易中心",
        "base_url": "https://ggzy.gxzf.gov.cn",
        "paths": ["/zbgg/", "/zhbgg/", "/cggg/"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "广西",
    },
    {
        "code": "hainan",
        "name": "海南省公共资源交易中心",
        "base_url": "https://ggzy.hainan.gov.cn",
        "paths": ["/ggzyjy/jyxx/003001/003001002/jyxx_list.html", "/ggzyjy/jyxx/003001/003001006/jyxx_list.html", "/ggzyjy/jyxx/003001/003001005/jyxx_list.html"],
        "detail_pattern": r"view|detail|info|content|html",
        "industry_hint": "",
        "region_hint": "海南",
        "render_type": "list",
    },
]

MAX_PAGES = 3
MAX_DAYS_BACK = 7


def is_blocked_page(text: str) -> bool:
    """检查页面内容是否被阻断"""
    blocked = ["403", "404", "禁止访问", "访问被拒绝", "Forbidden", "Not Found",
               "Bad Gateway", "502", "503", "504", "页面访问提示", "暂停访问",
               "WAF", "安全拦截", "访问受限"]
    return any(kw in text for kw in blocked)


def get_page_text(html: str) -> str:
    """从 HTML 提取纯文本"""
    text = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', text).strip()


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
        if href.startswith("javascript") or href == "#" or href == "":
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
        context_text = html[ctx_start:ctx_end]
        context_plain = get_page_text(context_text)

        date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', context_plain)
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


def extract_detail_from_html(html: str, url: str, region_hint: str) -> dict:
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
                r'(编号)[：:]?\s*([A-Z0-9\-_]{8,})']:
        m = re.search(pat, text)
        if m:
            code = m.group(2).strip()[:50] if len(m.groups()) > 1 else m.group(1).strip()[:50]
            break

    # 预算
    budget = ""
    m = re.search(r'预算[：:]?\s*([0-9,.]+)\s*万元', text)
    if m:
        budget = m.group(1).replace(",", "")

    # 采购人
    buyer = ""
    for pat in [r'(采购人|招标人|采购单位|业主)[：:]?\s*([^\s]{2,40})']:
        m = re.search(pat, text)
        if m:
            buyer = m.group(2).strip()
            if buyer:
                break

    # 截止日期
    deadline = ""
    m = re.search(r'(开标时间|投标截止|提交投标文件截止|递交投标文件截止)[^\\n]*?(\d{4}-\d{2}-\d{2})', text)
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
    ]
    for pat, name in method_pats:
        if re.search(pat, title) or re.search(pat, text[:1000]):
            method = name
            break

    # 行业
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
        source_name=f"公共资源交易-{region_hint}" if region_hint else "公共资源交易",
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


def crawl_site(site: dict) -> list:
    """爬取单个省份站点"""
    base_url = site["base_url"]
    site_name = site["name"]
    region_hint = site["region_hint"]
    site_items = []

    print(f"\n{'='*50}")
    print(f"🏛️  {site_name} ({base_url})")
    print(f"{'='*50}")

    # 测试连通性
    print(f"  🔗 测试连接...", end=" ", flush=True)
    index_html = proxy_fetch_html(base_url, timeout=20)
    if not index_html or is_blocked_page(index_html[:500]):
        print(f"❌ 不可达或被阻断")
        return site_items
    print(f"✅ ({len(index_html)} chars)")

    # 尝试各路径
    for path in site["paths"]:
        print(f"\n  路径: {path}")
        for pg in range(1, MAX_PAGES + 1):
            if pg == 1:
                url = f"{base_url}{path}"
            else:
                url = f"{base_url}{path}index_{pg}.html"

            html = proxy_fetch_html(url, timeout=20)
            if not html:
                if pg == 1:
                    print(f"  → 无法访问")
                else:
                    print(f"  → 第 {pg} 页空白")
                break

            entries = extract_list_items(html, url)
            if not entries:
                if pg == 1:
                    print(f"  → 无条目")
                else:
                    print(f"  → 第 {pg} 页无条目")
                break

            print(f"  📄 page={pg}: {len(entries)} 条")

            cutoff = (datetime.now() - timedelta(days=MAX_DAYS_BACK)).strftime("%Y-%m-%d")

            for entry in entries:
                if entry["date"] and entry["date"] < cutoff:
                    continue

                print(f"  → {entry['title'][:50]}...", end=" ", flush=True)
                detail_html = proxy_fetch_html(entry["url"], timeout=20)
                if not detail_html:
                    print(f"❌ (无法访问)")
                    continue

                detail = extract_detail_from_html(detail_html, entry["url"], region_hint)
                if detail:
                    site_items.append(detail)
                    print(f"✅")
                else:
                    print(f"❌ (解析失败)")

                random_delay(0.5, 1.5)

    return site_items


def main():
    parser = argparse.ArgumentParser(description="省级公共资源交易中心爬虫")
    parser.add_argument("--provinces", type=str, default="",
                        help="指定省份代码（逗号分隔），如 zj,gd,sd")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"🔍 省级公共资源交易中心爬虫 (CF代理版) · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    # 筛选要爬取的省份
    if args.provinces:
        selected_codes = set(args.provinces.split(","))
        sites = [s for s in PROVINCE_SITES if s["code"] in selected_codes]
        print(f"📋 指定省份: {', '.join(s['code'] for s in sites)} ({len(sites)}个)")
    else:
        sites = PROVINCE_SITES
        print(f"📋 全部 {len(sites)} 个站点")

    all_new_items = []
    failed_sites = []

    for site in sites:
        try:
            items = crawl_site(site)
            all_new_items.extend(items)
            if not items:
                failed_sites.append(site["code"])
        except Exception as e:
            print(f"  ⚠ {site['name']} 失败: {e}")
            failed_sites.append(site["code"])
        random_delay(1.0, 2.0)

    # 结果汇总
    successful = [s["code"] for s in sites if s["code"] not in failed_sites]
    print(f"\n{'='*50}")
    print(f"✅ 成功站点 ({len(successful)}): {', '.join(successful) if successful else '无'}")
    print(f"⚠️ 失败站点 ({len(failed_sites)}): {', '.join(failed_sites) if failed_sites else '无'}")
    print(f"📊 共爬取 {len(all_new_items)} 条新标讯")

    if all_new_items:
        append_bids(all_new_items, "省级公共资源交易中心")

    print(f"{'='*50}")


if __name__ == "__main__":
    main()
