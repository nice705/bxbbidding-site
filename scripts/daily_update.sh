#!/bin/bash
# 标讯宝 · 每日数据更新调度器
# 依次运行所有爬虫，合并数据到 bids.json
# 用法: bash scripts/daily_update.sh

set -e
cd "$(dirname "$0")"
DIR="$(dirname "$0")/.."
cd "$(dirname "$0")"
echo "========================================="
echo "  标讯宝 每日数据更新 · $(date '+%Y-%m-%d %H:%M')"
echo "========================================="

# 记录开始时间，用于统计
START=$(date +%s)

# 运行结果
PASS=0
FAIL=0
FAILED_SPIDERS=""

run_spider() {
    local name="$1"
    local script="$2"
    local timeout="${3:-300}"

    echo ""
    echo "─── 🕷️  $name ───"
    if timeout "$timeout" python3 "$script"; then
        echo "  ✅ $name 完成"
        PASS=$((PASS + 1))
    else
        local exit_code=$?
        echo "  ❌ $name 失败 (exit=$exit_code)"
        FAIL=$((FAIL + 1))
        FAILED_SPIDERS="$FAILED_SPIDERS $name"
    fi
}

# ── 1. 政府采购网 (requests, 无头) ──
run_spider "政府采购网"   "scripts/spider_ccgp.py" 600

# ── 2. 招标投标公共服务平台 (requests, 无头) ──
run_spider "招标投标平台" "scripts/spider_cebpub.py" 600

# ── 3. 招标投标公共服务平台 深度版 (Playwright) ──
run_spider "招标投标深度" "scripts/spider_cebpub_playwright.py" 600

# ── 4. 中国国际招标网 (Playwright) ──
run_spider "中国国际招标网" "scripts/spider_chinabidding.py" 300

# ── 5. 军队采购网 (Playwright + 代理) ──
run_spider "军队采购网"   "scripts/spider_plap.py" 120

# ── 6. 国家电网 (Playwright + 代理) ──
run_spider "国家电网"     "scripts/spider_sgcc.py" 120

# ── 7. 省级公共资源交易中心 (Playwright + 代理) ──
run_spider "省级公共资源" "scripts/spider_provinces.py" 300

# ── 8. 央企采购平台 (Playwright + 代理) ──
run_spider "央企采购平台" "scripts/spider_operators.py" 300

# ── 统计 ──
DURATION=$(( $(date +%s) - START ))
echo ""
echo "========================================="
echo "  更新完成"
echo "  耗时: ${DURATION}s"
echo "  成功: $PASS | 失败: $FAIL"
if [ -n "$FAILED_SPIDERS" ]; then
    echo "  失败列表:$FAILED_SPIDERS"
fi
echo "========================================="

# 显示数据统计
python3 -c "
import json
with open('data/bids.json') as f:
    data = json.load(f)
bids = data['bids']
today = data.get('todayCount', 0)
from collections import Counter
srcs = Counter(b['source'] for b in bids)
print(f'数据文件: {len(bids)} 条 (今日 {today} 条)')
for s, c in srcs.most_common():
    print(f'  {c:>6,d}  {s}')
"
