import json
import os

DETAIL_JSON = "data/bids-detail.json"
OUTPUT_DIR = "detail"

os.system("rm -rf " + OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(DETAIL_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

bids = data["bids"] if isinstance(data, dict) and "bids" in data else (data if isinstance(data, list) else [])

count = 0
for bid in bids:
    bid_id = bid.get("id")
    if not bid_id:
        continue
    safe_id = str(bid_id).replace("/", "_").replace("?", "_")

    title = bid.get("title") or "标讯详情"
    source = bid.get("source") or ""
    date = bid.get("date") or ""
    region = bid.get("region") or ""
    source_url = bid.get("source_url") or "#"
    content = bid.get("content") or ""

    att_html = ""
    attachments = bid.get("attachments") or []
    for a in attachments:
        if isinstance(a, dict):
            url = a.get("url") or ""
            name = a.get("name") or url.split("/")[-1]
            att_html += '<a href="' + url + '">' + name + '</a> '
        elif isinstance(a, str) and a:
            fname = a.split("/")[-1] if "/" in a else a
            att_html += '<a href="' + a + '">' + fname + '</a> '
    if not att_html:
        att_html = "无"

    html = '<!DOCTYPE html>\n'
    html += '<html>\n<head>\n'
    html += '<meta charset="UTF-8">\n'
    html += '<title>' + title + '</title>\n'
    html += '<style>\n'
    html += 'body{font-family:sans-serif;max-width:1000px;margin:20px auto;padding:0 20px;}\n'
    html += '.meta{color:#666;font-size:14px;}\n'
    html += '.content{line-height:1.8;}\n'
    html += '.attachments{margin:20px 0;padding:10px;background:#f5f5f5;}\n'
    html += 'a{color:#0366d6;}\n'
    html += 'table{border-collapse:collapse;width:100%;}\n'
    html += 'th,td{border:1px solid #ddd;padding:8px;}\n'
    html += 'th{background:#f2f2f2;}\n'
    html += '</style>\n</head>\n<body>\n'
    html += '<h1>' + title + '</h1>\n'
    html += '<div class="meta">\n'
    html += '<span>来源：' + source + '</span> | '
    html += '<span>日期：' + date + '</span> | '
    html += '<span>地区：' + region + '</span>\n</div>\n'
    html += '<div class="source"><a href="' + source_url + '" target="_blank">\u67e5\u770b\u6e90\u7ad9</a></div>\n'
    html += '<div class="content">' + content + '</div>\n'
    html += '<div class="attachments">\n<strong>\u9644\u4ef6\uff1a</strong>\n' + att_html + '\n</div>\n'
    html += '</body>\n</html>'

    detail_dir = os.path.join(OUTPUT_DIR, safe_id)
    os.makedirs(detail_dir, exist_ok=True)
    with open(os.path.join(detail_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    count += 1
    if count % 200 == 0:
        print("generated " + str(count) + "...")

print("total: " + str(count) + " detail pages")
