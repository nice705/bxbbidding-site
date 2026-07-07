#!/usr/bin/env python3
import json
with open('/home/hermes/bid-crawler/data/enriched-bids.json') as f:
    data = json.load(f)
bids = data.get('bids', [])
long_bids = [b for b in bids if b.get('is_bidding', True) and len(str(b.get('content', '') or '')) >= 200]
short_bids = [b for b in bids if b.get('is_bidding', True) and b not in long_bids]
for b in long_bids + short_bids:
    if b.get('date') is None: b['date'] = ''
long_bids.sort(key=lambda x: str(x.get('date', '')), reverse=True)
short_bids.sort(key=lambda x: str(x.get('date', '')), reverse=True)
homepage = long_bids[:200]
if len(homepage) < 200:
    homepage += short_bids[:200-len(homepage)]
seen = set()
dedup = []
for b in homepage:
    key = b.get('title', '')[:50] + b.get('sourceUrl', '')[:50]
    if key not in seen:
        seen.add(key)
        dedup.append(b)
homepage = dedup[:200]
from datetime import date
today_str = date.today().strftime('%Y-%m-%d')
today = sum(1 for b in homepage if str(b.get('date', '')).startswith(today_str))
with open('/home/hermes/bid-crawler/data/enriched-homepage.json', 'w') as f:
    json.dump({'updatedAt': today_str, 'todayCount': today, 'total': len(homepage), 'bids': homepage}, f, ensure_ascii=False)
print(f'首页: {len(homepage)} 条（今日 {today}）')
