#!/bin/bash
echo "[$(date)] cebpub_bulk 开始" >> ~/projects/bidding-site/logs/cebpub_bulk.log
cd ~/projects/bidding-site
timeout 1800 python3 scripts/spider_cebpub_bulk.py >> logs/cebpub_bulk.log 2>&1
echo "[$(date)] cebpub_bulk 完成" >> logs/cebpub_bulk.log
