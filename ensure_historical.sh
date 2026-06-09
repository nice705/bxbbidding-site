#!/bin/bash
# 自愈检查：如果 cebpub 历史蜘蛛没在跑，从最新月份开始逆序重跑
LOG_DIR=~/projects/bidding-site/logs
DATA_DIR=~/projects/bidding-site/data
mkdir -p "$LOG_DIR"

# 检查蜘蛛是否在跑
if ps aux | grep -v grep | grep -q 'spider_cebpub_historical'; then
    echo "[$(date '+%Y-%m-%d %H:%M')] Spider already running, skipping" >> "$LOG_DIR/ensure_historical.log"
    exit 0
fi

# 检查 bids-cebpub.json 是否已有数据
if [ -f "$DATA_DIR/bids-cebpub.json" ]; then
    COUNT=$(python3 -c "import json; d=json.load(open('$DATA_DIR/bids-cebpub.json')); print(len(d.get('bids', d if isinstance(d, list) else [])))" 2>/dev/null)
    if [ "$COUNT" -gt 50000 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M')] Already $COUNT records, running remaining months only" >> "$LOG_DIR/ensure_historical.log"
        screen -dmS cebpub bash -c 'cd ~/projects/bidding-site && python3 scripts/spider_cebpub_historical.py --remaining >> logs/cebpub_historical_$(date +%%Y%%m%%d_%%H%%M).log 2>&1'
        exit 0
    fi
fi

# 正常启动（从最新月份开始逆向扫描）
screen -dmS cebpub bash -c 'cd ~/projects/bidding-site && python3 scripts/spider_cebpub_historical.py >> logs/cebpub_historical_$(date +%%Y%%m%%d_%%H%%M).log 2>&1'
echo "[$(date '+%Y-%m-%d %H:%M')] Spider started" >> "$LOG_DIR/ensure_historical.log"
