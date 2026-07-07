import sqlite3, time
DB_PATH = '/home/hermes/bid-crawler/bid_crawler.db'
def generate_sitemap(limit=5000):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM bids_v2 WHERE id IS NOT NULL ORDER BY crawled_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    with open('sitemap.xml', 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.write(' <url><loc>https://qgbxb.com/</loc><priority>1.0</priority></url>\n')
        f.write(' <url><loc>https://qgbxb.com/list</loc><priority>0.9</priority></url>\n')
        for (bid_id,) in rows:
            f.write(f' <url><loc>https://qgbxb.com/detail?id={bid_id}</loc><priority>0.7</priority></url>\n')
        f.write('</urlset>\n')
    print(f"✅ sitemap.xml 已生成（{len(rows)} 条详情页）")
if __name__ == '__main__':
    generate_sitemap()
