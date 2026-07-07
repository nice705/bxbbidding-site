import json, os
from jinja2 import Template
with open('data/enriched-bids.json', 'r') as f:
    data = json.load(f)
bids = data['bids'] if isinstance(data, dict) else data
os.makedirs('static_detail', exist_ok=True)
tmpl = Template("""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{{ title }}</title></head>
<body><h1>{{ title }}</h1><div>{{ content|safe }}</div></body>
</html>""")
count = 0
for bid in bids[:2000]:
    bid_id = bid.get('id', '')
    title = bid.get('title', '')
    if bid_id and title:
        html = tmpl.render(title=title, content=bid.get('content', ''))
        with open(f'static_detail/{bid_id}.html', 'w') as f:
            f.write(html)
        count += 1
print(f"✅ {count} 个静态详情页已生成")
