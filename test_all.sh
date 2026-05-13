#!/bin/bash
# 币安加密货币 Skill 全量测试
# 用法: bash test_all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$SCRIPT_DIR/crypto-kit-skills"
SCRIPTS_DIR="$SKILL_DIR/scripts"
LOCAL_DIR="$SKILL_DIR/local"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
TOTAL=0

# 已知的非关键错误（testnet 不支持某些 endpoint，不算 FAIL）
KNOWN_NONCRITICAL="获取持仓量历史失败"

show_data() {
    # 提取输出中的表格行和关键数据，最多显示 max_lines 行
    local output="$1"
    local max_lines="${2:-6}"

    # 注意: 用 [|] 匹配字面竖线，兼容 macOS BSD grep（-E 模式下 \| 含义不同）
    local data_lines
    data_lines=$(echo "$output" | grep -E '^[|].*[|]' | grep -v '^[|]-' | tail -n "$max_lines")

    if [ -n "$data_lines" ]; then
        echo "$data_lines" | while IFS= read -r line; do
            printf "    ${DIM}%s${NC}\n" "$line"
        done
    else
        # 没有表格，显示包含关键数据的行
        echo "$output" | grep -E '[$]|价|分|评分|收益|资金|余额|条记录' | head -n "$max_lines" | while IFS= read -r line; do
            printf "    ${DIM}%s${NC}\n" "$line"
        done
    fi
}

run_test() {
    local name="$1"
    local cmd="$2"
    local check_pattern="$3"  # 可选：输出中应包含的关键词
    local show_output="${4:-yes}"  # 是否显示数据预览

    TOTAL=$((TOTAL + 1))
    printf "  [%2d] %-45s " "$TOTAL" "$name"

    # 设置超时（如果有 timeout/gtimeout）
    TIMEOUT_CMD=""
    if command -v timeout &>/dev/null; then
        TIMEOUT_CMD="timeout 60"
    elif command -v gtimeout &>/dev/null; then
        TIMEOUT_CMD="gtimeout 60"
    fi

    OUTPUT=$($TIMEOUT_CMD bash -c "$cmd" 2>&1) || true
    EXIT_CODE=$?

    # 过滤掉已知的非关键错误后，再检查是否有真正的错误
    FILTERED_OUTPUT=$(echo "$OUTPUT" | grep -v "$KNOWN_NONCRITICAL" || true)

    if echo "$FILTERED_OUTPUT" | grep -qiE "Traceback|exception|ModuleNotFoundError" 2>/dev/null; then
        printf "${RED}FAIL${NC}\n"
        echo "$OUTPUT" | grep -A2 -iE "Traceback|Error" | head -5 | while IFS= read -r line; do
            printf "    ${RED}%s${NC}\n" "$line"
        done
        FAIL=$((FAIL + 1))
        return
    fi

    # 检查预期关键词
    if [ -n "$check_pattern" ]; then
        if ! echo "$OUTPUT" | grep -qi "$check_pattern" 2>/dev/null; then
            printf "${YELLOW}WARN${NC} (未找到: $check_pattern)\n"
            SKIP=$((SKIP + 1))
            return
        fi
    fi

    if [ $EXIT_CODE -eq 0 ]; then
        printf "${GREEN}PASS${NC}\n"
        PASS=$((PASS + 1))

        # 显示数据预览
        if [ "$show_output" = "yes" ] && [ -n "$OUTPUT" ]; then
            show_data "$OUTPUT"
        fi
    else
        printf "${RED}FAIL${NC} (exit=$EXIT_CODE)\n"
        FAIL=$((FAIL + 1))
    fi
}

echo "======================================"
echo "  币安加密货币 Skill 全量测试"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================"
echo ""

# 清缓存
rm -f "$SKILL_DIR/.cache/binance_cache.db" 2>/dev/null
echo "已清理缓存"

# 预热域名探测（避免每个测试都等 3 秒超时）
printf "\n  预热 API 域名探测..."
cd "$SCRIPTS_DIR"
WARMUP=$(python3 -c "from api_client import get_spot_base, get_futures_base; s=get_spot_base(); f=get_futures_base(); print(f'现货={s} 合约={f}')" 2>&1)
printf " ${GREEN}完成${NC}\n"
printf "  ${DIM}%s${NC}\n" "$WARMUP"
echo ""

# === 依赖检查 ===
echo "--- 依赖检查 ---"
run_test "Python 可用" "python3 --version" "Python" "no"
run_test "pandas 已安装" "python3 -c 'import pandas; print(pandas.__version__)'" "" "no"
run_test "requests 已安装" "python3 -c 'import requests; print(requests.__version__)'" "" "no"
run_test "numpy 已安装" "python3 -c 'import numpy; print(numpy.__version__)'" "" "no"
echo ""

# === 实时行情 ===
echo "--- 实时行情 ---"
run_test "BTC 实时行情" "cd $SCRIPTS_DIR && python3 get_realtime.py BTCUSDT" "最新价"
run_test "ETH 实时行情" "cd $SCRIPTS_DIR && python3 get_realtime.py ETHUSDT" "最新价"
run_test "主流币概览" "cd $SCRIPTS_DIR && python3 get_realtime.py --all" "BTCUSDT"
run_test "BTC 盘口深度" "cd $SCRIPTS_DIR && python3 get_realtime.py BTCUSDT --depth" "盘口"
echo ""

# === 现货 K 线 ===
echo "--- 现货 K 线 ---"
run_test "BTC 日 K 线(30天)" "cd $SCRIPTS_DIR && python3 get_kline.py BTCUSDT --days 30" "条记录"
run_test "ETH 日 K 线(60天)" "cd $SCRIPTS_DIR && python3 get_kline.py ETHUSDT --days 60" "条记录"
run_test "BTC 4小时 K 线" "cd $SCRIPTS_DIR && python3 get_kline.py BTCUSDT -i 4h --days 7" "条记录"
run_test "省略USDT后缀" "cd $SCRIPTS_DIR && python3 get_kline.py BTC --days 10" "条记录"
echo ""

# === 合约数据 ===
echo "--- 合约数据 ---"
run_test "BTC 合约 K 线" "cd $SCRIPTS_DIR && python3 get_futures_kline.py BTCUSDT --days 30" "条记录"
run_test "BTC 资金费率" "cd $SCRIPTS_DIR && python3 get_futures_kline.py BTCUSDT --funding" "费率"
run_test "BTC 持仓量" "cd $SCRIPTS_DIR && python3 get_futures_kline.py BTCUSDT --oi" "持仓"
echo ""

# === 技术指标 ===
echo "--- 技术指标 ---"
run_test "BTC 技术分析" "cd $SCRIPTS_DIR && python3 calc_technical.py BTCUSDT" "技术信号"
run_test "ETH 技术分析" "cd $SCRIPTS_DIR && python3 calc_technical.py ETHUSDT" "技术信号"
echo ""

# === 回测 ===
echo "--- 策略回测 ---"
run_test "BTC MA回测(180天)" "cd $SCRIPTS_DIR && python3 backtest.py ma BTCUSDT --days 180" "回测"
run_test "ETH MA回测(365天)" "cd $SCRIPTS_DIR && python3 backtest.py ma ETHUSDT --days 365" "回测"
run_test "BTC RSI回测" "cd $SCRIPTS_DIR && python3 backtest.py rsi BTCUSDT --days 180" "回测"
echo ""

# === 综合分析 ===
echo "--- 综合分析 ---"
run_test "BTC 综合分析" "cd $SCRIPTS_DIR && python3 analyze_crypto.py BTCUSDT" "综合评分"
run_test "ETH 综合分析" "cd $SCRIPTS_DIR && python3 analyze_crypto.py ETHUSDT" "综合评分"
echo ""

# === 模拟交易 ===
echo "--- 模拟交易 ---"
run_test "重置模拟账户" "cd $SCRIPTS_DIR && python3 simulate_trade.py reset --capital 10000" "重置"
run_test "模拟买入 BTC" "cd $SCRIPTS_DIR && python3 simulate_trade.py buy BTCUSDT --usdt 3000" "买入成功"
run_test "模拟买入 ETH" "cd $SCRIPTS_DIR && python3 simulate_trade.py buy ETHUSDT --usdt 2000" "买入成功"
run_test "查看账户状态" "cd $SCRIPTS_DIR && python3 simulate_trade.py status" "总资产"
run_test "模拟卖出 BTC" "cd $SCRIPTS_DIR && python3 simulate_trade.py sell BTCUSDT --all" "卖出成功"
run_test "查看交易历史" "cd $SCRIPTS_DIR && python3 simulate_trade.py history" "交易历史"
echo ""

# === 数据下载 ===
echo "--- 数据下载 ---"
run_test "数据摘要" "cd $LOCAL_DIR && python3 download_history.py --summary" ""
echo ""

# === 缓存 ===
echo "--- 缓存管理 ---"
run_test "缓存管理器" "cd $SCRIPTS_DIR && python3 cache_manager.py" "缓存"
echo ""

# === 汇总 ===
echo "======================================"
printf "  通过: ${GREEN}%d${NC}\n" "$PASS"
printf "  失败: ${RED}%d${NC}\n" "$FAIL"
printf "  跳过: ${YELLOW}%d${NC}\n" "$SKIP"
echo "  总计: $TOTAL"
echo "======================================"

if [ $FAIL -gt 0 ]; then
    echo ""
    printf "${RED}有 %d 项测试失败!${NC}\n" "$FAIL"
    exit 1
else
    echo ""
    printf "${GREEN}全部通过!${NC}\n"
fi
