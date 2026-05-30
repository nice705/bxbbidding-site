#!/bin/bash
cd ~/projects/bidding-site
python3 -c "
import json, gzip, os
# 统计各种来源
total = 0
cebpub = 0
d = 'data'
# bids.json
if os.path.exists('data/bids.json'):
    with open('data/bids.json') as f:
        data = json.load(f)
        total = len(data.get('bids',[]))
# bids-cebpub.json  
if os.path.exists('data/bids-cebpub.json'):
    with open('data/bids-cebpub.json') as f:
        data = json.load(f)
        cebpub = len(data.get('bids',[]))
from datetime import datetime
print(f'{datetime.now().strftime(\"%Y-%m-%d %H:%M\")} | cebpub: {cebpub} | total: {total}')
"
