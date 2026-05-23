#!/usr/bin/env python3
"""标讯宝 Sitemap 生成器

用法: python3 scripts/build-sitemap.py

从 data/bids.json 读取所有标讯 ID，生成 sitemap.xml
每次更新数据后运行此脚本重新生成
"""

import json
from datetime import datetime
from pathlib import Path

SITE = 'https://bidding-site.pages.dev'
TODAY = datetime.now().strftime('%Y-%m-%d')
ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / 'data' / 'bids.json'
OUTPUT = ROOT / 'sitemap.xml'

def main():
    with open(DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)

    urls = []

    # 首页
    urls.append(f'''  <url>
    <loc>{SITE}/</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>''')

    # 列表页
    urls.append(f'''  <url>
    <loc>{SITE}/list.html</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>''')

    # 详情页
    for bid in data.get('bids', []):
        bid_id = bid.get('id', '')
        date = bid.get('date', TODAY)
        urls.append(f'''  <url>
    <loc>{SITE}/detail.html?id={bid_id}</loc>
    <lastmod>{date}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>''')

    sitemap = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>'''

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(sitemap)

    count = len(data.get('bids', [])) + 2
    print(f'✅ sitemap.xml 已更新（{count} 个 URL → {OUTPUT}）')

if __name__ == '__main__':
    main()
