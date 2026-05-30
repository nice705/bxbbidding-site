#!/bin/bash
# 阿里云标讯宝快速爬虫 - 每2小时
# CCGP + CEBPub（快速增量）

cd /home/hermes/projects/bidding-site
LOG_DIR=/home/hermes/projects/bidding-site/logs
mkdir -p $LOG_DIR
NOW=$(date +%Y-%m-%d_%H:%M)

echo "[$NOW] === 快速爬取 ===" >> $LOG_DIR/spider_hourly.log

START=$(date -d "1 day ago" +%Y-%m-%d)
END=$(date +%Y-%m-%d)

# 1. CCGP
echo "[$NOW] CCGP..." >> $LOG_DIR/spider_hourly.log
timeout 120 python3 -u scripts/spider_ccgp.py --method search --start $START --end $END 2>&1 | tail -5 >> $LOG_DIR/spider_hourly.log

# 2. CEBPub
echo "[$NOW] CEBPub..." >> $LOG_DIR/spider_hourly.log
timeout 120 python3 -u scripts/spider_cebpub.py --start $START --end $END 2>&1 | tail -5 >> $LOG_DIR/spider_hourly.log

# 3. 标记
python3 scripts/update_timestamp.py
echo "[$NOW] === 完成 ===" >> $LOG_DIR/spider_hourly.log
