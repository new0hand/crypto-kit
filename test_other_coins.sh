#!/bin/bash
# 测试其他币种
cd "$(dirname "$0")/binance-crypto-skills/scripts"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

echo "=== 实时行情 ==="
for coin in SOLUSDT DOGEUSDT XRPUSDT ADAUSDT AVAXUSDT; do
    printf "${CYAN}$coin${NC}: "
    python3 get_realtime.py $coin 2>&1 | grep '最新价' | head -1 | sed 's/.*| //'
done

echo ""
echo "=== SOL 技术分析 ==="
python3 calc_technical.py SOLUSDT 2>&1 | grep -E '技术信号|MA7|MACD|RSI|趋势'

echo ""
echo "=== DOGE 综合分析 ==="
python3 analyze_crypto.py DOGEUSDT 2>&1 | grep -E '综合评分|当前价格|建议'

echo ""
echo "=== XRP MA回测 180天 ==="
python3 backtest.py ma XRPUSDT --days 180 2>&1 | grep -E '策略收益|买入持有|交易次数|胜率'

echo ""
echo "=== SOL 模拟交易 ==="
python3 simulate_trade.py buy SOLUSDT --usdt 1000 2>&1
echo ""
python3 simulate_trade.py status 2>&1 | grep -E '总资产|SOL|ETH|BTC|余额'
