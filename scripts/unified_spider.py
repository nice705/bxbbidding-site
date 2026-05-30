#!/usr/bin/env python3
"""
标讯宝 · 31省全覆盖统一爬虫

策略：
  1. CCGP扫描 → 各省政府采购网首页，抓取带关键词的链接
  2. GGZY扫描 → 各省公共资源交易中心
  3. 厅局级扫描 → 各省教育厅/体育局/卫健委等
  4. 国家级平台 → 中央级CCGP + 招标网 + bidcenter

输出：stdout JSON（兼容bids.json格式）
      或 --save 直接写入 data/bids.json

运行：
  python3 scripts/unified_spider.py                         # 扫全部
  python3 scripts/unified_spider.py --provinces 广东,浙江    # 指定省
  python3 scripts/unified_spider.py --sources ccgp,ggzy      # 指定源类型
  python3 scripts/unified_spider.py --days 3                 # 近3天
  python3 scripts/unified_spider.py --save                   # 保存到bids.json
"""

import json, os, re, sys, time, hashlib
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.province_config import (
    PROVINCES, NATIONAL_PLATFORMS, DEPT_URLS, GGZY_EXTRA,
    KEYWORDS, EXCLUDE_KEYWORDS, ccgp_urls, dept_urls, all_provinces
)

# ── 配置 ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
TIMEOUT = 15   # 单页超时
DELAY = 1.0    # 请求间隔(秒)
MAX_PER_PAGE = 50  # 单页最多采集


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def make_id(title, url):
    """生成唯一ID"""
    raw = f"{title}|{url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def try_fetch(url, timeout=TIMEOUT):
    """安全抓取，返回soup或None"""
    try:
        r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        if r.status_code != 200:
            return None
        if len(r.text) < 500:
            return None  # 可能被跳转到验证页
        if "访问受限" in r.text or "频繁" in r.text or "请输入验证码" in r.text:
            return None
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def extract_links(soup, base_url, province_name, source_name):
    """从soup中提取带关键词的招标链接"""
    items = []
    seen = set()
    for a in soup.select("a[href]"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if len(title) < 10 or title in seen:
            continue
        if not any(k in title for k in KEYWORDS):
            continue
        # 排除非招标内容（通知/办法/问卷等）
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
            "sourceUrl": href,
            "date": today_str(),
            "id": make_id(title, href),
            "category": "招标公告",
            "content": "",
        })
        if len(items) >= MAX_PER_PAGE:
            break
    return items


# ── 策略1: CCGP 各省政府采购网 ───────────────────────
def scan_ccgp_provinces(province_filter=None):
    """扫描省份CCGP首页（可指定省份列表）"""
    items = []
    for name, url in ccgp_urls():
        if province_filter and name not in province_filter:
            continue
        soup = try_fetch(url)
        if not soup:
            print(f"  [CCGP] {name} ❌ 不可达或验证拦截", file=sys.stderr)
            continue
        links = extract_links(soup, url, name, f"{name}政府采购网")
        if links:
            print(f"  [CCGP] {name} → {len(links)}条", file=sys.stderr)
        else:
            print(f"  [CCGP] {name} → 0条(无匹配关键词)", file=sys.stderr)
        items.extend(links)
        time.sleep(DELAY)
    return items


# ── 策略2: GGZY 公共资源交易 ──────────────────────────
def scan_ggzy():
    """扫描各省公共资源交易中心"""
    items = []
    # 国家级
    for plat in NATIONAL_PLATFORMS:
        if plat["type"] != "GGZY":
            continue
        soup = try_fetch(plat["url"])
        if not soup:
            continue
        links = extract_links(soup, plat["url"], "全国", plat["name"])
        items.extend(links)
        time.sleep(DELAY)
    
    # 省级
    for province, url in GGZY_EXTRA.items():
        soup = try_fetch(url)
        if not soup:
            print(f"  [GGZY] {province} ❌ 不可达", file=sys.stderr)
            continue
        links = extract_links(soup, url, province, f"{province}公共资源交易中心")
        if links:
            print(f"  [GGZY] {province} → {len(links)}条", file=sys.stderr)
        items.extend(links)
        time.sleep(DELAY)
    return items


# ── 策略3: 国家级平台 ─────────────────────────────────
def scan_national():
    """国家级平台扫描"""
    items = []
    for plat in NATIONAL_PLATFORMS:
        if plat["type"] == "GGZY":
            continue  # GGZY已在上方处理
        soup = try_fetch(plat["url"])
        if not soup:
            print(f"  [NTL] {plat['name']} ❌ 不可达", file=sys.stderr)
            continue
        links = extract_links(soup, plat["url"], "全国", plat["name"])
        if links:
            print(f"  [NTL] {plat['name']} → {len(links)}条", file=sys.stderr)
        items.extend(links)
        time.sleep(DELAY)
    return items


# ── 策略4: 厅局级（各省厅局主页） ─────────────────────
def scan_departments():
    """扫描各省厅局级单位首页"""
    items = []
    depts = dept_urls()
    for province, url in depts:
        domain = urlparse(url).netloc
        source_name = f"{province}{list(DEPT_URLS.get(province,[])).index(url)+1}局"
        
        soup = try_fetch(url)
        if not soup:
            print(f"  [DEPT] {province}({urlparse(url).path[:15]}) ❌ 不可达", file=sys.stderr)
            continue
        links = extract_links(soup, url, province, source_name)
        if links:
            print(f"  [DEPT] {province}({len(links)}条)", file=sys.stderr)
        items.extend(links)
        time.sleep(DELAY)
    return items


# ── 继承原CCGP蜘蛛（深度爬取） ────────────────────────
def scan_ccgp_deep():
    """调用已有的spider_ccgp.py（需要本地环境）"""
    try:
        from scripts.spider_ccgp import crawl_ccgp
        items = crawl_ccgp(days_back=1)
        print(f"  [CCGP-DEEP] 深度爬取完成 → {len(items)}条", file=sys.stderr)
        return items
    except Exception as e:
        print(f"  [CCGP-DEEP] 失败: {e}", file=sys.stderr)
        return []


# ── 合并到bids.json ────────────────────────────────────
def merge_to_bids(new_items, data_file=DATA_FILE):
    """将新采集的条目合并到bids.json（去重）"""
    # 读取现有数据
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {"bids": [], "updatedAt": "", "todayCount": 0}
    
    existing_ids = {b.get("id", "") for b in existing["bids"]}
    
    added = 0
    for item in new_items:
        item_id = item.get("id", make_id(item.get("title",""), item.get("sourceUrl", item.get("url",""))))
        item["id"] = item_id
        if item_id not in existing_ids:
            existing["bids"].append(item)
            existing_ids.add(item_id)
            added += 1
    
    # 更新元数据
    existing["updatedAt"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    today_bids = [b for b in existing["bids"] if b.get("date") == today_str()]
    existing["todayCount"] = len(today_bids)
    
    # 写回
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, separators=(",", ":"))
    
    return added


# ── 主入口 ─────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="标讯宝31省全覆盖爬虫")
    parser.add_argument("--provinces", help="限定省份，逗号分隔（如：广东,浙江）")
    parser.add_argument("--sources", help="源类型：ccgp,ggzy,dept,national 逗号分隔")
    parser.add_argument("--days", type=int, default=1, help="回溯天数（默认1）")
    parser.add_argument("--save", action="store_true", help="保存到data/bids.json")
    parser.add_argument("--ccgp-deep", action="store_true", help="同时运行CCGP深层爬虫")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    args = parser.parse_args()
    
    if not args.quiet:
        print(f"🔍 标讯宝全覆盖爬虫 — {datetime.now().strftime('%m-%d %H:%M')}", file=sys.stderr)
    
    all_items = []
    sources_enabled = set(args.sources.split(",")) if args.sources else {"ccgp","ggzy","dept","national"}
    
    # 解析省份过滤
    province_filter = set(args.provinces.split(",")) if args.provinces else None
    
    # 策略1: CCGP各省
    if "ccgp" in sources_enabled:
        label = f"指定{len(province_filter)}省" if province_filter else "31省"
        if not args.quiet:
            print(f"\n📌 [1/4] 扫描{label}CCGP采购网...", file=sys.stderr)
        items = scan_ccgp_provinces(province_filter)
        all_items.extend(items)
    
    # 策略1b: CCGP深层
    if args.ccgp_deep:
        if not args.quiet:
            print(f"\n📌 [1b] CCGP深层爬取...", file=sys.stderr)
        items = scan_ccgp_deep()
        all_items.extend(items)
    
    # 策略2: GGZY公共资源
    if "ggzy" in sources_enabled:
        if not args.quiet:
            print(f"\n📌 [2/4] 公共资源交易中心...", file=sys.stderr)
        items = scan_ggzy()
        all_items.extend(items)
    
    # 策略3: 国家级平台
    if "national" in sources_enabled:
        if not args.quiet:
            print(f"\n📌 [3/4] 国家级平台...", file=sys.stderr)
        items = scan_national()
        all_items.extend(items)
    
    # 策略4: 厅局级
    if "dept" in sources_enabled:
        if not args.quiet:
            print(f"\n📌 [4/4] 厅局级单位...", file=sys.stderr)
        items = scan_departments()
        all_items.extend(items)
    
    # 去重
    seen = set()
    unique = []
    for item in all_items:
        item_id = item.get("id", "")
        if item_id not in seen:
            seen.add(item_id)
            unique.append(item)
    
    if not args.quiet:
        print(f"\n{'='*50}", file=sys.stderr)
        print(f"✅ 本次采集: {len(unique)} 条（去重后）", file=sys.stderr)
    
    # 输出
    if args.save:
        added = merge_to_bids(unique)
        if not args.quiet:
            print(f"  新增到bids.json: {added} 条", file=sys.stderr)
    else:
        print(json.dumps(unique, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
