#!/usr/bin/env python3
"""标讯宝 · 广东全省公共资源交易平台API爬虫

使用广东省统一公共资源交易平台 REST API 获取招标公告。
API 无需认证，直接 HTTP GET 即可。

运行:
  python3 scripts/spider_gdggzy.py
  python3 scripts/spider_gdggzy.py --save
"""
import json, os, sys, time, hashlib
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.province_config import KEYWORDS, EXCLUDE_KEYWORDS
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")
API_BASE = "https://ygp.gdzwfw.gov.cn/ggzy-portal/center/apis"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://ygp.gdzwfw.gov.cn/",
}

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def make_id(title, url):
    raw = f"{title}|{url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]

def fetch_agenda(days=1):
    """获取招标公告日程"""
    end = datetime.now()
    start = end - timedelta(days=days)
    params = {
        "pageNo": 1, "pageSize": 50,
        "tradingTypeCode": "", "regionCode": "44",
        "startTime": start.strftime("%Y%m%d000000"),
        "endTime": end.strftime("%Y%m%d235959"),
        "siteCode": "44",
    }
    all_items = []
    seen_records = set()
    
    max_pages = 8
    while params["pageNo"] <= max_pages:
        try:
            r = requests.get(f"{API_BASE}/trading-notice/agenda", params=params, headers=HEADERS, timeout=15)
            data = r.json()
            if data.get("errcode") != 0 or not data.get("data"):
                params["pageNo"] += 1
                time.sleep(0.3)
                continue
            page_data = data["data"].get("pageData", [])
            if not page_data:
                break
            for item in page_data:
                rid = item.get("recordId", "")
                if rid and rid not in seen_records:
                    seen_records.add(rid)
                    title = item.get("projectName", "")
                    if len(title) < 8:
                        continue
                    all_items.append({
                        "title": title,
                        "source": "广东省公共资源交易平台",
                        "province": "广东",
                        "url": f"https://ygp.gdzwfw.gov.cn/#/44/new/jygg/v3/{item.get('noticeType','')}?noticeId={rid}",
                        "date": today_str(),
                        "id": make_id(title, rid),
                        "category": f"{item.get('tradingType','')}-{item.get('noticeType','')}",
                        "content": json.dumps(item, ensure_ascii=False),
                        "region": item.get("regionName", "广东省").strip(),
                        "projectCode": item.get("projectCode", ""),
                    })
            params["pageNo"] += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  [GDGGZY] 第{params['pageNo']}页重试: {e}", file=sys.stderr)
            params["pageNo"] += 1
            time.sleep(1)
    
    print(f"  [GDGGZY] 广东API → {len(all_items)}条", file=sys.stderr)
    return all_items

def merge_to_bids(new_items):
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {"bids": [], "updatedAt": "", "todayCount": 0}
    existing_ids = {b.get("id", "") for b in existing["bids"]}
    added = 0
    for item in new_items:
        iid = item.get("id", "")
        if iid not in existing_ids:
            existing["bids"].append(item)
            existing_ids.add(iid)
            added += 1
    existing["updatedAt"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    existing["todayCount"] = sum(1 for b in existing["bids"] if b.get("date") == today_str())
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, separators=(",", ":"))
    return added

def main():
    import argparse
    parser = argparse.ArgumentParser(description="广东公共资源交易平台API爬虫")
    parser.add_argument("--days", type=int, default=1, help="回溯天数")
    parser.add_argument("--save", action="store_true", help="保存到bids.json")
    args = parser.parse_args()
    
    print(f"🔍 广东公共资源交易平台API — {today_str()}", file=sys.stderr)
    items = fetch_agenda(days=args.days)
    
    if args.save:
        added = merge_to_bids(items)
        print(f"  新增到bids.json: {added}条", file=sys.stderr)
    else:
        print(json.dumps(items, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
