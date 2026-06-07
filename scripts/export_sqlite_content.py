#!/usr/bin/env python3
"""导出 crawl_v4 SQLite 正文到 JSON，供 merge_all.py 使用
输出格式: {url: {title, date, source, province, content, content_score}}
正文未匹配时会作为新条目追加到 bids.json

v2: 新增 content_score 字段
"""
import json, sqlite3, sys, os

DB_PATH = '/home/hermes/bid-crawler/bid_crawler.db'
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sqlite_content.json')

def main():
    if not os.path.exists(DB_PATH):
        print(f'DB not found: {DB_PATH}', file=sys.stderr)
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT url, title, date, source, province, content, content_score "
        "FROM bids WHERE content IS NOT NULL AND length(content) > 200"
    )
    rows = cur.fetchall()
    conn.close()
    
    result = {}
    for url, title, date_str, source, province, content, content_score in rows:
        if not url or not content:
            continue
        result[url] = {
            "title": title or "",
            "date": date_str or "",
            "source": source or province or "省级公共资源",
            "content": content,
            "content_score": content_score or 0,
        }
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)
    
    with_score = sum(1 for v in result.values() if v.get('content_score', 0) > 0)
    print(f'Exported {len(result)} records ({with_score} with content_score) to {OUTPUT}', file=sys.stderr)
    print(OUTPUT)

if __name__ == '__main__':
    main()
