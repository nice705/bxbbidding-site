#!/bin/bash
# 标讯宝每日全覆盖 - 凌晨05:00运行
# 31省CCGP + GGZY + 省CCGP深度 + 18省厅局

cd /home/hermes/projects/bidding-site
LOG_DIR=/home/hermes/projects/bidding-site/logs
mkdir -p $LOG_DIR
NOW=$(date +%Y-%m-%d_%H:%M)

echo "[$NOW] === 开始每日全覆盖 ===" >> $LOG_DIR/spider_daily.log

# 1. 31省CCGP + 国家级
echo "[$NOW] 31省CCGP..." >> $LOG_DIR/spider_daily.log
timeout 300 python3 -u scripts/unified_spider.py --sources ccgp,ggzy,national --save 2>&1 | tail -3 >> $LOG_DIR/spider_daily.log

# 2. 31省厅局级
echo "[$NOW] 31省厅局..." >> $LOG_DIR/spider_daily.log
timeout 300 python3 -u scripts/unified_spider.py --sources dept --save 2>&1 | tail -3 >> $LOG_DIR/spider_daily.log

# 3. 各省GGZY公共资源交易中心
echo "[$NOW] GGZY..." >> $LOG_DIR/spider_daily.log
timeout 300 python3 -u scripts/ggzy_spider.py --save 2>&1 | tail -3 >> $LOG_DIR/spider_daily.log

# 4b. 广东全省公共资源交易平台API
echo "[$NOW] 广东全省API..." >> $LOG_DIR/spider_daily.log
timeout 120 python3 -u scripts/spider_gdggzy.py --days 3 --save 2>&1 | tail -3 >> $LOG_DIR/spider_daily.log

# 4. 省CCGP深度（采购意向/需求公开等）
echo "[$NOW] 省CCGP深度..." >> $LOG_DIR/spider_daily.log
timeout 300 python3 -u scripts/province_deep_spider.py --save 2>&1 | tail -3 >> $LOG_DIR/spider_daily.log

# 标记
python3 scripts/update_timestamp.py
echo "[$NOW] === 完成 ===" >> $LOG_DIR/spider_daily.log
