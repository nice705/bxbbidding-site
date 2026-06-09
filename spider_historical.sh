#!/bin/bash
cd ~/projects/bidding-site
LOG="logs/cebpub_historical_$(date '+%Y%m%d_%H%M').log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] cebpub 全量扫描启动" >> ""
python3 scripts/spider_cebpub_historical.py >> "" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成" >> ""
