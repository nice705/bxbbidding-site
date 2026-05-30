#!/usr/bin/env python3
"""
标讯宝 · 各省CCGP深度爬虫（采购意向/需求公开/合同公告等）

中央CCGP站缺失的频道，各省独立站点上可能有：
  - 采购意向 (cgyx/yxgk)
  - 需求公开 (xqgs)
  - 合同公告 (htgg)
  - 结果公告 (jggg)
  - 单一来源 (dyly)
  等

策略：对每个省CCGP站，尝试常见频道URL模式并爬取。

运行：
  python3 scripts/province_deep_spider.py
  python3 scripts/province_deep_spider.py --save
"""

import json, os, sys, time, hashlib
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.province_config import PROVINCES, KEYWORDS, EXCLUDE_KEYWORDS

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
TIMEOUT = 6      # 短超时，卡住的不等
DELAY = 0.2     # 短间隔

# 各省CCGP站点上要探测的额外频道
# 优先：采购意向(cgyx) + 需求公示(xqgs) + 合同公告(htgg)
EXTRA_CHANNELS = [
    "cgyx",     # 采购意向
    "xqgs",     # 需求公示
    "htgg",     # 合同公告
]
CHANNEL_NAMES = {
    "cgyx": "采购意向", "xqgs": "需求公示",
    "htgg": "合同公告",
}


def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def make_id(title, url):
    return hashlib.md5(f"{title}|{url}".encode()).hexdigest()[:12]

def try_fetch(url):
    try:
        r = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True, verify=False)
        if r.status_code == 200 and len(r.text) > 2000:
            return r.text
    except: pass
    return None

def extract_items(html, base_url, province_name, source_name):
    items = []
    seen = set()
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if len(title) < 10 or title in seen: continue
        if not any(k in title for k in KEYWORDS): continue
        if any(k in title for k in EXCLUDE_KEYWORDS): continue
        seen.add(title)
        if href and not href.startswith("http"):
            try: href = urljoin(base_url, href)
            except: continue
        items.append({
            "title": title, "source": source_name, "province": province_name,
            "url": href, "date": today_str(), "id": make_id(title, href),
            "category": "招标公告", "content": "",
        })
        if len(items) >= 20: break
    return items

def probe_province(province_name, ccgp_url):
    """对一个省CCGP站，探测所有额外频道"""
    found_channels = []
    for channel in EXTRA_CHANNELS:
        ch_name = CHANNEL_NAMES.get(channel, channel)
        # 尝试多种URL模式
        patterns = [
            f"{ccgp_url}{channel}/",
            f"{ccgp_url}{channel}/index.htm",
            f"{ccgp_url}cgyx/",  # 采购意向
        ]
        # 去重
        seen_urls = set()
        for url in patterns:
            if url in seen_urls: continue
            seen_urls.add(url)
            html = try_fetch(url)
            if html:
                found_channels.append((ch_name, url))
                break
        time.sleep(DELAY)
    return found_channels

def crawl():
    """主爬取流程"""
    print(f"\n🔍 省CCGP深度爬虫 — {datetime.now().strftime('%H:%M')}", file=sys.stderr)
    
    all_items = []
    total_found = 0
    total_channels = 0
    
    for name, info in PROVINCES.items():
        ccgp_url = info["ccgp_url"]
        print(f"\n[{name}] 探测额外频道...", file=sys.stderr)
        
        channels = probe_province(name, ccgp_url)
        if channels:
            print(f"  发现 {len(channels)} 个频道: {', '.join(c[0] for c in channels)}", file=sys.stderr)
            total_channels += len(channels)
            for ch_name, ch_url in channels:
                html = try_fetch(ch_url)
                if not html: continue
                source = f"{name}政府采购网/{ch_name}"
                items = extract_items(html, ch_url, name, source)
                if items:
                    print(f"    {ch_name}: {len(items)}条", file=sys.stderr)
                all_items.extend(items)
                time.sleep(DELAY)
        else:
            print(f"  无额外频道可访问", file=sys.stderr)
    
    # 去重
    seen = set()
    unique = []
    for item in all_items:
        item_id = item.get("id", "")
        if item_id not in seen:
            seen.add(item_id)
            unique.append(item)
    
    print(f"\n✅ 共探测 {len(PROVINCES)} 省, 发现 {total_channels} 个频道, 采集 {len(unique)} 条", file=sys.stderr)
    return unique

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

def main():
    import argparse
    parser = argparse.ArgumentParser(description="省CCGP深度爬虫")
    parser.add_argument("--save", action="store_true", help="保存到bids.json")
    args = parser.parse_args()
    
    items = crawl()
    if args.save:
        added = merge_to_bids(items)
        print(f"  新增到bids.json: {added}条", file=sys.stderr)
    else:
        print(json.dumps(items, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
