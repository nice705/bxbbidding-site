import json
with open('data/enriched-bids.json', 'r') as f:
    data = json.load(f)
bids = data['bids'] if isinstance(data, dict) else data
with open('sitemap.xml', 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    f.write(' <url><loc>https://qgbxb.com/</loc><priority>1.0</priority></url>\n')
    f.write(' <url><loc>https://qgbxb.com/list</loc><priority>0.9</priority></url>\n')
    for bid in bids[:5000]:
        bid_id = bid.get('id', '')
        if bid_id:
            f.write(f' <url><loc>https://qgbxb.com/detail?id={bid_id}</loc><priority>0.7</priority></url>\n')
    f.write('</urlset>')
print(f"✅ sitemap.xml 生成，{min(len(bids),5000)} 个详情页")
