#!/usr/bin/env python3
"""标记bids.json最新更新时间"""
import json, os
from datetime import datetime

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bids.json")
if not os.path.exists(path):
    print("❌ bids.json not found")
    exit(1)

with open(path, "r", encoding="utf-8") as f:
    d = json.load(f)

now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "+08:00"
d["updatedAt"] = now

# 今日计数
today = datetime.now().strftime("%Y-%m-%d")
d["todayCount"] = sum(1 for b in d.get("bids", []) if b.get("date") == today)

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, separators=(",", ":"))

print(f"✅ 已更新: {len(d.get(chr(98)+chr(105)+chr(100)+chr(115),[]))}条, {now}")
