#!/usr/bin/env python3
"""
标讯宝 · 各省公共资源交易中心深度爬虫

策略：
  1. 探测已知GGZY URL模式，发现可达站点
  2. 对可达站点爬取招标公告列表
  3. 支持翻页（常见模式：分页/滚动）
  4. 输出兼容bids.json格式

运行：
  python3 scripts/ggzy_spider.py                     # 探测+爬取全部
  python3 scripts/ggzy_spider.py --probe-only        # 只探测不爬取
  python3 scripts/ggzy_spider.py --save              # 保存到bids.json
"""

import json, os, re, sys, time, hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.province_config import PROVINCES, KEYWORDS, EXCLUDE_KEYWORDS

# ── 配置 ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
TIMEOUT = 12
DELAY = 0.3
MAX_PAGES = 5  # 每站抓取页数
MAX_PER_PAGE = 20


# ── 各省GGZY URL清单（已知+推测模式）──
GGZY_URLS = {
    # 直辖市
    "北京": ["https://ggzyfw.beijing.gov.cn/"],
    "天津": ["https://www.tjggzy.com/"],
    "上海": ["https://www.shggzy.com/"],
    "重庆": ["https://www.cqggzy.com/"],
    # 华北
    "河北": ["http://ggzy.hebei.gov.cn/", "http://www.hbggzyjy.com/", "http://www.hebpr.gov.cn/"],
    "山西": ["https://www.sxggzyjy.cn/"],
    "内蒙古": ["https://ggzyjy.nmg.gov.cn/"],
    # 东北
    "辽宁": ["http://ggzy.ln.gov.cn/"],
    "吉林": ["https://www.jlggzyjy.cn/", "http://www.jl.gov.cn/ggzy/"],
    "黑龙江": ["http://www.hlj.gov.cn/ggzy/"],
    # 华东
    "江苏": ["http://jsggzy.jszwfw.gov.cn/"],
    "浙江": ["https://ggzy.zj.gov.cn/"],
    "安徽": ["http://ggzy.ah.gov.cn/"],
    "福建": ["https://ggzyfw.fujian.gov.cn/"],
    "江西": ["http://ggzy.jiangxi.gov.cn/"],
    "山东": ["https://ggzyjy.shandong.gov.cn/"],
    # 华中
    "河南": ["https://www.hnggzyjy.cn/"],
    "湖北": ["http://www.hbggzyfwpt.cn/"],
    "湖南": ["http://ggzy.hunan.gov.cn/"],
    # 华南
    "广东": ["https://ygp.gdzwfw.gov.cn/"],
    "广西": ["http://ggzy.jgswj.gxzf.gov.cn/gxggzy/"],
    "海南": ["http://ggzy.hainan.gov.cn/"],
    # 西南
    "四川": ["https://ggzyjy.sc.gov.cn/"],
    "贵州": ["http://ggzy.guizhou.gov.cn/"],
    "云南": ["https://ggzy.yn.gov.cn/"],
    "西藏": ["http://ggzy.xizang.gov.cn/"],
    # 西北
    "陕西": ["http://ggzy.shaanxi.gov.cn/"],
    "甘肃": ["https://ggzyjy.gansu.gov.cn/"],
    "青海": ["http://www.qhggzyjy.gov.cn/"],
    "宁夏": ["https://ggzyjy.fzggw.nx.gov.cn/", "http://www.nxggzyjy.org/", "http://www.ccgp-ningxia.gov.cn/"],
    "新疆": ["http://ggzy.xinjiang.gov.cn/"],
    # 重点城市
    "广州": ["https://www.gzggzy.cn/"],
    "深圳": ["http://zfcg.szggzy.com:8081/", "https://www.szzfcg.cn/", "https://www.szggzy.com/"],
    "成都": ["https://www.cdggzy.com/"],
}


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def make_id(title, url):
    raw = f"{title}|{url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def try_fetch(url, timeout=TIMEOUT, ssl_context=None):
    try:
        kwargs = dict(headers=HEADERS, timeout=timeout, follow_redirects=True, verify=False)
        if ssl_context:
            kwargs["verify"] = ssl_context
        r = httpx.get(url, **kwargs)
        if r.status_code != 200:
            return None
        if len(r.text) < 1000:
            return None
        return r.text
    except Exception:
        return None


import ssl as ssl_mod

def beijing_ssl_context():
    """北京GGZY需要特殊cipher绕过ECDHE问题"""
    ctx = ssl_mod.create_default_context()
    ctx.set_ciphers("AES128-GCM-SHA256:AES256-GCM-SHA384")
    ctx.check_hostname = False
    ctx.verify_mode = ssl_mod.CERT_NONE
    return ctx


def extract_links(html, base_url, province_name, source_name):
    items = []
    seen = set()
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if len(title) < 10 or title in seen:
            continue
        if not any(k in title for k in KEYWORDS):
            continue
        if any(k in title for k in EXCLUDE_KEYWORDS):
            continue
        seen.add(title)
        if href and not href.startswith("http"):
            try:
                href = urljoin(base_url, href)
            except:
                continue
        items.append({
            "title": title,
            "source": source_name,
            "province": province_name,
            "url": href,
            "date": today_str(),
            "id": make_id(title, href),
            "category": "招标公告",
            "content": "",
        })
        if len(items) >= MAX_PER_PAGE:
            break
    return items


def find_listing_urls(html, base_url):
    """在首页找招标公告列表页URL"""
    listing_urls = []
    soup = BeautifulSoup(html, "html.parser")
    keywords = ["招标公告", "采购公告", "中标公告", "交易公告", "通知公告",
                "政府采购", "招标信息", "采购信息", "交易信息"]
    for a in soup.select("a[href]"):
        text = a.get_text(strip=True)
        href = a.get("href", "")
        if any(k in text for k in keywords) and href:
            if not href.startswith("http"):
                href = urljoin(base_url, href)
            listing_urls.append((text, href))
    return listing_urls[:5]


# ── 探测所有GGZY站点 ─────────────────────────────────
def probe_all():
    print(f"\n📡 探测{len(GGZY_URLS)}个地区共{sum(len(v) for v in GGZY_URLS.values())}个GGZY站点...", file=sys.stderr)
    beijing_ctx = beijing_ssl_context()
    working = {}
    for province, urls in GGZY_URLS.items():
        for url in urls:
            ctx = beijing_ctx if province == "北京" else None
            html = try_fetch(url, ssl_context=ctx)
            if html:
                working[province] = url
                print(f"  ✅ {province}: {url}", file=sys.stderr)
                break
            else:
                print(f"  ❌ {province}: {url}", file=sys.stderr)
            time.sleep(DELAY)
    print(f"  可达: {len(working)}/{len(GGZY_URLS)}个地区", file=sys.stderr)
    return working


# ── 爬取GGZY站点 ──────────────────────────────────────
def crawl_working(working):
    all_items = []
    beijing_ctx = beijing_ssl_context()
    for province, url in working.items():
        name = f"{province}公共资源交易中心"
        ctx = beijing_ctx if province == "北京" else None
        html = try_fetch(url, ssl_context=ctx)
        if not html:
            continue
        
        # 首页链接提取
        items = extract_links(html, url, province, name)
        print(f"  [GGZY] {province} → 首页{len(items)}条", file=sys.stderr)
        all_items.extend(items)
        
        # 找列表页并爬
        listing_pages = find_listing_urls(html, url)
        for list_name, list_url in listing_pages[:3]:
            list_html = try_fetch(list_url, ssl_context=ctx)
            if not list_html:
                continue
            list_items = extract_links(list_html, list_url, province, f"{name}/{list_name[:10]}")
            if list_items:
                print(f"    ↪ {list_name[:12]} → {len(list_items)}条", file=sys.stderr)
            all_items.extend(list_items)
            time.sleep(DELAY)
        
        time.sleep(DELAY)
    
    # 去重
    seen = set()
    unique = []
    for item in all_items:
        item_id = item.get("id", "")
        if item_id not in seen:
            seen.add(item_id)
            unique.append(item)
    
    return unique


# ── 合并到bids.json ───────────────────────────────────
def merge_to_bids(new_items):
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {"bids": [], "updatedAt": "", "todayCount": 0}
    
    existing_ids = {b.get("id", "") for b in existing["bids"]}
    added = 0
    for item in new_items:
        item_id = item.get("id", "")
        if item_id not in existing_ids:
            existing["bids"].append(item)
            existing_ids.add(item_id)
            added += 1
    
    existing["updatedAt"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    existing["todayCount"] = sum(1 for b in existing["bids"] if b.get("date") == today_str())
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, separators=(",", ":"))
    return added


# ── 主入口 ─────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="标讯宝GGZY公共资源交易中心爬虫")
    parser.add_argument("--probe-only", action="store_true", help="只探测不爬取")
    parser.add_argument("--save", action="store_true", help="保存到bids.json")
    args = parser.parse_args()
    
    print(f"🔍 GGZY公共资源交易中心爬虫 — {datetime.now().strftime('%H:%M')}", file=sys.stderr)
    
    # 探测
    working = probe_all()
    if not working:
        print("❌ 无可达站点", file=sys.stderr)
        return
    
    if args.probe_only:
        print(f"探测完成。{len(working)}/37个地区可达。", file=sys.stderr)
        return
    
    # 爬取
    print(f"\n📥 开始爬取{len(working)}个可达站点...", file=sys.stderr)
    items = crawl_working(working)
    print(f"\n✅ 采集: {len(items)}条", file=sys.stderr)
    
    if args.save:
        added = merge_to_bids(items)
        print(f"  新增到bids.json: {added}条", file=sys.stderr)
    else:
        print(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
