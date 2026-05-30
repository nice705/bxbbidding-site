#!/usr/bin/env python3
"""分析被屏蔽的标讯数据"""
import json
from collections import Counter

d = json.load(open('/home/hemers/projects/bidding-site/data/bids.json'))
bids = d['bids']

blocked_kw = ['页面访问提示', '暂停访问', 'PDF 文件']

blocked = []
good = []
for b in bids:
    c = b.get('content', '')
    if not c or len(c) <= 100 or any(k in c for k in blocked_kw):
        blocked.append(b)
    else:
        good.append(b)

dates = sorted(set(b.get('date','') for b in blocked if b.get('date')))
print(f'被屏蔽: {len(blocked)} 条')
if dates:
    print(f'日期范围: {dates[0]} ~ {dates[-1]}')
print(f'真实内容: {len(good)} 条')

srcs = Counter(b.get('source','') for b in blocked)
print('\n按来源:')
for s, cnt in srcs.most_common():
    print(f'  {s}: {cnt} 条')

print('\n示例:', blocked[0]['title'][:50], '|', blocked[0].get('source',''))

ceb_ids = {b['id'] for b in blocked if b.get('source') == '招标投标公共服务平台'}
ccg_ids = {b['id'] for b in good if b.get('source') == '政府采购网'}
overlap = ceb_ids & ccg_ids
print(f'\ncebpub 被屏蔽: {len(ceb_ids)}')
print(f'ccgp 真实内容: {len(ccg_ids)}')
print(f'ID 交叉(同id出现): {len(overlap)}')

# 检查是否有同title的
ceb_titles = {b['title'] for b in blocked if b.get('source') == '招标投标公共服务平台'}
ccg_titles = {b['title'] for b in good if b.get('source') == '政府采购网'}
print(f'\ncebpub 标题数: {len(ceb_titles)}')
print(f'ccgp  标题数: {len(ccg_titles)}')
overlap_titles = ceb_titles & ccg_titles
print(f'标题交叉: {len(overlap_titles)}')
if overlap_titles:
    for t in list(overlap_titles)[:5]:
        print(f'  → {t[:60]}')
