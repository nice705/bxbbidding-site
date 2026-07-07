#!/usr/bin/env python3
"""正确合并 bids_v2 数据到 bids-full.json，然后写入 enriched-bids.json"""
import json, sqlite3, hashlib
from datetime import datetime

DB_PATH = '/home/hermes/bid-crawler/bid_crawler.db'
FULL_PATH = '/home/hermes/bid-crawler/data/bids-full.json'
ENRICHED_PATH = '/home/hermes/bid-crawler/data/enriched-bids.json'

def main():
    # 1. 读取 bids_v2
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT title, publish_date, body_html, body_text, attachments,
               source_url, platform, province, crawled_at
        FROM bids_v2
        WHERE source_url IS NOT NULL AND source_url != ''
        ORDER BY crawled_at DESC
    """)
    v2_rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    print(f"bids_v2: {len(v2_rows)} 条")

    # 2. 去重（保留正文最长的）
    v2_dedup = {}
    for r in v2_rows:
        url = r['source_url']
        body_len = len(r.get('body_text') or '')
        if url not in v2_dedup or body_len > len(v2_dedup[url].get('body_text', '')):
            v2_dedup[url] = r
    print(f"v2 去重后: {len(v2_dedup)} 条")

    # 3. 读取 bids-full.json
    with open(FULL_PATH, 'r', encoding='utf-8') as f:
        full_bids = json.load(f)
    full_list = full_bids if isinstance(full_bids, list) else full_bids.get('bids', [])
    print(f"bids-full.json: {len(full_list)} 条")

    # 4. 构建 sourceUrl 映射，并转换为 enriched 格式
    enriched = []
    full_url_set = set()
    
    for r in full_list:
        url = r.get('sourceUrl') or r.get('source_url') or r.get('url') or ''
        full_url_set.add(url)
        
        attachments_raw = r.get('attachments') or r.get('attachments_list') or []
        if isinstance(attachments_raw, str):
            try: attachments_raw = json.loads(attachments_raw)
            except: attachments_raw = []
        
        enriched.append({
            'id': r.get('id', hashlib.md5(url.encode()).hexdigest()[:15]),
            'title': r.get('title', ''),
            'sourceUrl': url,
            'date': r.get('date') or r.get('publish_date') or r.get('pub_date') or '',
            'source': r.get('source') or r.get('platform') or '',
            'content': r.get('content') or r.get('body_text') or '',
            'html': r.get('html') or r.get('body_html') or '',
            'method': r.get('method', ''),
            'region': r.get('region') or r.get('province') or '',
            'buyer': r.get('buyer', ''),
            'deadline': r.get('deadline', ''),
            'budget': r.get('budget', ''),
            'attachments': attachments_raw,
            'hasAttachment': len(attachments_raw) > 0,
            'is_bidding': r.get('is_bidding', True)
        })
    print(f"已转换 full: {len(enriched)} 条")

    # 5. 添加 v2 中不在 full 中的记录
    added = 0
    for url, r in v2_dedup.items():
        if url in full_url_set:
            continue  # 已在 full 中
        
        attachments_raw = r.get('attachments') or []
        if isinstance(attachments_raw, str):
            try: attachments_raw = json.loads(attachments_raw)
            except: attachments_raw = []
        
        enriched.append({
            'id': hashlib.md5(url.encode()).hexdigest()[:15],
            'title': r.get('title', ''),
            'sourceUrl': url,
            'date': r.get('publish_date', ''),
            'source': r.get('platform', ''),
            'content': r.get('body_text', ''),
            'html': r.get('body_html', ''),
            'method': '',
            'region': r.get('province', ''),
            'buyer': '',
            'deadline': '',
            'budget': '',
            'attachments': attachments_raw,
            'hasAttachment': len(attachments_raw) > 0,
            'is_bidding': True
        })
        added += 1
    print(f"新增 v2 专属: {added} 条")

    # 6. 写回
    output = {
        'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'todayCount': sum(1 for r in enriched if (r.get('date') or '').startswith('2026-07-03')),
        'total': len(enriched),
        'bids': enriched
    }
    with open(ENRICHED_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ enriched-bids.json 已更新: {len(enriched)} 条")
    with_body = sum(1 for r in enriched if len(r.get('content', '') or '') > 200)
    print(f"  有正文(>200字): {with_body}")
    with_att = sum(1 for r in enriched if r.get('hasAttachment'))
    print(f"  有附件: {with_att}")
    today_count = sum(1 for r in enriched if (r.get('date') or '').startswith('2026-07-03'))
    print(f"  今日(7月3日): {today_count}")

if __name__ == '__main__':
    main()
