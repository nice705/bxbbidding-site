#!/bin/bash
MONTH=$(date +%Y-%m)
cd ~/projects/bidding-site
python3 scripts/spider_cebpub_historical.py --month $MONTH >> logs/cron_cebpub.log 2>&1
echo "[$(date)] CEBPub 完成" >> logs/cron_cebpub.log
