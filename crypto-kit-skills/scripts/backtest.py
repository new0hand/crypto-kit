# -*- coding: utf-8 -*-
"""
加密货币策略回测

支持策略:
- ma: 双均线交叉策略（默认 MA7/MA25）
- rsi: RSI 超买超卖策略

用法:
    python backtest.py ma BTCUSDT
    python backtest.py ma BTCUSDT --days 365
    python backtest.py ma ETHUSDT --fast 7 --slow 25
    python backtest.py rsi BTCUSDT --oversold 30 --overbought 70
    python backtest.py ma BTCUSDT --interval 4h --days 90
    python backtest.py ma --all                          # 批量回测 49 只主流币
    python backtest.py ma --all --days 730 --top 10      # 最近2年，只显示前10
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("请先安装依赖: pip install pandas numpy")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DIR = os.path.join(SCRIPT_DIR, "..", "local")
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, LOCAL_DIR)
from get_kline import get_kline
from calc_technical import calc_ma, calc_rsi

# 主流币列表（从 download_history.py 同步）
try:
    from download_history import MAINSTREAM_SYMBOLS
except ImportError:
    MAINSTREAM_SYMBOLS = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT", "LINKUSDT",
    ]


def backtest_ma(df: pd.DataFrame, fast: int = 7, slow: int = 25,
                initial_capital: float = 10000) -> dict:
    """双均线交叉回测"""
    df = calc_ma(df, periods=[fast, slow])
    df = df.dropna(subset=[f'MA{fast}', f'MA{slow}']).copy()

    if len(df) < 2:
        return {'error': '数据不足'}

    capital = initial_capital
    position = 0.0  # 持仓数量
    trades = []
    holding = False

    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        price = curr['close']
        dt = curr['datetime'].strftime('%Y-%m-%d %H:%M') if pd.notna(curr.get('datetime')) else str(i)

        # 金叉买入
        if prev[f'MA{fast}'] <= prev[f'MA{slow}'] and curr[f'MA{fast}'] > curr[f'MA{slow}'] and not holding:
            position = capital / price
            trades.append({
                'type': 'BUY', 'date': dt, 'price': price,
                'amount': position, 'capital': capital
            })
            holding = True

        # 死叉卖出
        elif prev[f'MA{fast}'] >= prev[f'MA{slow}'] and curr[f'MA{fast}'] < curr[f'MA{slow}'] and holding:
            capital = position * price
            trades.append({
                'type': 'SELL', 'date': dt, 'price': price,
                'amount': position, 'capital': capital
            })
            position = 0.0
            holding = False

    # 如果最后还持仓，按最后收盘价计算
    final_price = df.iloc[-1]['close']
    if holding:
        capital = position * final_price

    # 统计
    total_return = (capital - initial_capital) / initial_capital * 100
    buy_hold_return = (final_price - df.iloc[0]['close']) / df.iloc[0]['close'] * 100

    # 计算胜率
    wins = 0
    losses = 0
    for i in range(0, len(trades) - 1, 2):
        if i + 1 < len(trades):
            if trades[i + 1]['capital'] > trades[i]['capital']:
                wins += 1
            else:
                losses += 1

    win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0

    # 最大回撤
    equity_curve = []
    temp_capital = initial_capital
    temp_position = 0.0
    temp_holding = False
    for i in range(len(df)):
        curr = df.iloc[i]
        if i > 0:
            prev_row = df.iloc[i - 1]
            if prev_row[f'MA{fast}'] <= prev_row[f'MA{slow}'] and curr[f'MA{fast}'] > curr[f'MA{slow}'] and not temp_holding:
                temp_position = temp_capital / curr['close']
                temp_holding = True
            elif prev_row[f'MA{fast}'] >= prev_row[f'MA{slow}'] and curr[f'MA{fast}'] < curr[f'MA{slow}'] and temp_holding:
                temp_capital = temp_position * curr['close']
                temp_position = 0.0
                temp_holding = False
        if temp_holding:
            equity_curve.append(temp_position * curr['close'])
        else:
            equity_curve.append(temp_capital)

    max_drawdown = 0
    peak = equity_curve[0]
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_drawdown:
            max_drawdown = dd

    return {
        'strategy': f'MA{fast}/MA{slow} 交叉',
        'initial_capital': initial_capital,
        'final_capital': round(capital, 2),
        'total_return': round(total_return, 2),
        'buy_hold_return': round(buy_hold_return, 2),
        'trades_count': len(trades),
        'win_rate': round(win_rate, 1),
        'max_drawdown': round(max_drawdown, 2),
        'trades': trades,
        'start_date': df.iloc[0]['datetime'].strftime('%Y-%m-%d') if pd.notna(df.iloc[0].get('datetime')) else '',
        'end_date': df.iloc[-1]['datetime'].strftime('%Y-%m-%d') if pd.notna(df.iloc[-1].get('datetime')) else '',
    }


def backtest_rsi(df: pd.DataFrame, period: int = 14,
                 oversold: int = 30, overbought: int = 70,
                 initial_capital: float = 10000) -> dict:
    """RSI 超买超卖回测"""
    df = calc_rsi(df, periods=[period])
    rsi_col = f'RSI{period}'
    df = df.dropna(subset=[rsi_col]).copy()

    if len(df) < 2:
        return {'error': '数据不足'}

    capital = initial_capital
    position = 0.0
    trades = []
    holding = False

    for i in range(1, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i - 1]
        price = curr['close']
        dt = curr['datetime'].strftime('%Y-%m-%d %H:%M') if pd.notna(curr.get('datetime')) else str(i)

        # RSI 从超卖区回升 → 买入
        if prev[rsi_col] < oversold and curr[rsi_col] >= oversold and not holding:
            position = capital / price
            trades.append({'type': 'BUY', 'date': dt, 'price': price, 'amount': position, 'capital': capital})
            holding = True

        # RSI 进入超买区 → 卖出
        elif curr[rsi_col] > overbought and holding:
            capital = position * price
            trades.append({'type': 'SELL', 'date': dt, 'price': price, 'amount': position, 'capital': capital})
            position = 0.0
            holding = False

    final_price = df.iloc[-1]['close']
    if holding:
        capital = position * final_price

    total_return = (capital - initial_capital) / initial_capital * 100
    buy_hold_return = (final_price - df.iloc[0]['close']) / df.iloc[0]['close'] * 100

    wins = 0
    losses = 0
    for i in range(0, len(trades) - 1, 2):
        if i + 1 < len(trades):
            if trades[i + 1]['capital'] > trades[i]['capital']:
                wins += 1
            else:
                losses += 1

    win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0

    return {
        'strategy': f'RSI{period} ({oversold}/{overbought})',
        'initial_capital': initial_capital,
        'final_capital': round(capital, 2),
        'total_return': round(total_return, 2),
        'buy_hold_return': round(buy_hold_return, 2),
        'trades_count': len(trades),
        'win_rate': round(win_rate, 1),
        'max_drawdown': 0,  # 简化
        'trades': trades,
        'start_date': df.iloc[0]['datetime'].strftime('%Y-%m-%d') if pd.notna(df.iloc[0].get('datetime')) else '',
        'end_date': df.iloc[-1]['datetime'].strftime('%Y-%m-%d') if pd.notna(df.iloc[-1].get('datetime')) else '',
    }


def format_result(result: dict, symbol: str) -> str:
    """格式化回测结果"""
    if 'error' in result:
        return f"回测失败: {result['error']}"

    trend_total = "🟢" if result['total_return'] >= 0 else "🔴"
    trend_bh = "🟢" if result['buy_hold_return'] >= 0 else "🔴"

    lines = [
        f"# {symbol} 策略回测报告\n",
        f"**策略**: {result['strategy']}",
        f"**回测区间**: {result['start_date']} ~ {result['end_date']}\n",
        "## 回测结果\n",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 初始资金 | ${result['initial_capital']:,.2f} |",
        f"| 最终资金 | ${result['final_capital']:,.2f} |",
        f"| 策略收益 | {trend_total} {result['total_return']:+.2f}% |",
        f"| 买入持有收益 | {trend_bh} {result['buy_hold_return']:+.2f}% |",
        f"| 交易次数 | {result['trades_count']} |",
        f"| 胜率 | {result['win_rate']:.1f}% |",
        f"| 最大回撤 | {result['max_drawdown']:.2f}% |",
        "",
    ]

    # 交易明细
    if result['trades']:
        lines.append("## 交易明细\n")
        lines.append("| 操作 | 日期 | 价格 | 资金 |")
        lines.append("|------|------|------|------|")
        for t in result['trades'][-20:]:  # 最近 20 笔
            icon = "🟢 买入" if t['type'] == 'BUY' else "🔴 卖出"
            lines.append(f"| {icon} | {t['date']} | ${t['price']:,.2f} | ${t['capital']:,.2f} |")

        if len(result['trades']) > 20:
            lines.append(f"\n> 仅显示最近 20 笔，共 {len(result['trades'])} 笔交易")

    lines.append("\n---")
    lines.append("> 以上回测结果仅供参考，历史表现不代表未来收益。加密货币波动极大，请谨慎投资。")

    return "\n".join(lines)


def backtest_all(strategy: str, interval: str, days: int, capital: float,
                 fast: int = 7, slow: int = 25,
                 rsi_period: int = 14, oversold: int = 30, overbought: int = 70,
                 top: int = 0) -> str:
    """批量回测所有主流币，输出对比排名表"""
    import time as _time

    # 检查本地数据
    local_count = 0
    if os.path.exists(DATA_DIR):
        local_count = len([f for f in os.listdir(DATA_DIR) if f.endswith('.parquet')])

    symbols = MAINSTREAM_SYMBOLS
    strategy_name = f"MA{fast}/{slow}" if strategy == 'ma' else f"RSI{rsi_period}"

    print(f"# 主流币批量回测\n")
    print(f"**策略**: {strategy_name}  |  **周期**: {interval}  |  **回测天数**: {days}  |  **本地数据**: {local_count} 只")
    print(f"**币种数**: {len(symbols)}")
    print()

    results = []
    t0 = _time.time()

    for i, sym in enumerate(symbols, 1):
        sym = sym.upper()
        short = sym.replace('USDT', '')
        # 静默获取数据
        sys.stdout = open(os.devnull, 'w')
        try:
            df = get_kline(sym, interval, days)
        finally:
            sys.stdout = sys.__stdout__

        if df is None or len(df) < 30:
            print(f"  [{i}/{len(symbols)}] {short:<8} ⏭ 数据不足")
            continue

        if strategy == 'ma':
            r = backtest_ma(df, fast=fast, slow=slow, initial_capital=capital)
        else:
            r = backtest_rsi(df, period=rsi_period, oversold=oversold,
                             overbought=overbought, initial_capital=capital)

        if 'error' in r:
            print(f"  [{i}/{len(symbols)}] {short:<8} ❌ {r['error']}")
            continue

        r['symbol'] = short
        results.append(r)

        trend = "🟢" if r['total_return'] >= 0 else "🔴"
        src = "本地" if local_count > 0 else "API"
        print(f"  [{i}/{len(symbols)}] {short:<8} {trend} {r['total_return']:>+8.2f}%  (持有 {r['buy_hold_return']:>+.1f}%)  [{src}]")

    elapsed = _time.time() - t0

    if not results:
        return "没有有效回测结果"

    # 按收益排序
    results.sort(key=lambda x: x['total_return'], reverse=True)

    # 输出排名表
    lines = [
        f"\n{'='*70}",
        f"\n## {strategy_name} 策略回测排名（{results[0].get('start_date', '')} ~ {results[0].get('end_date', '')}）\n",
    ]

    display = results[:top] if top > 0 else results

    lines.append("| 排名 | 币种 | 策略收益 | 买入持有 | 超额收益 | 交易次数 | 胜率 | 最大回撤 |")
    lines.append("|------|------|----------|----------|----------|----------|------|----------|")

    for rank, r in enumerate(display, 1):
        trend = "🟢" if r['total_return'] >= 0 else "🔴"
        excess = r['total_return'] - r['buy_hold_return']
        excess_icon = "📈" if excess > 0 else "📉"
        lines.append(
            f"| {rank} | **{r['symbol']}** | {trend} {r['total_return']:+.2f}% "
            f"| {r['buy_hold_return']:+.2f}% | {excess_icon} {excess:+.2f}% "
            f"| {r['trades_count']} | {r['win_rate']:.0f}% | {r['max_drawdown']:.1f}% |"
        )

    if top > 0 and len(results) > top:
        lines.append(f"\n> 仅显示前 {top} 名，共 {len(results)} 只币种参与回测")

    # 统计摘要
    avg_return = sum(r['total_return'] for r in results) / len(results)
    positive = sum(1 for r in results if r['total_return'] > 0)
    beat_hold = sum(1 for r in results if r['total_return'] > r['buy_hold_return'])

    lines.append(f"\n## 统计摘要\n")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 参与回测 | {len(results)} 只 |")
    lines.append(f"| 策略盈利 | {positive}/{len(results)} ({positive/len(results)*100:.0f}%) |")
    lines.append(f"| 跑赢持有 | {beat_hold}/{len(results)} ({beat_hold/len(results)*100:.0f}%) |")
    lines.append(f"| 平均策略收益 | {avg_return:+.2f}% |")
    lines.append(f"| 最佳 | {results[0]['symbol']} ({results[0]['total_return']:+.2f}%) |")
    lines.append(f"| 最差 | {results[-1]['symbol']} ({results[-1]['total_return']:+.2f}%) |")
    lines.append(f"| 耗时 | {elapsed:.0f} 秒 |")

    lines.append("\n---")
    lines.append("> 以上回测结果仅供参考，历史表现不代表未来收益。")

    output = "\n".join(lines)
    print(output)
    return output


def main():
    parser = argparse.ArgumentParser(description='加密货币策略回测')
    parser.add_argument('strategy', choices=['ma', 'rsi'], help='策略: ma(均线交叉), rsi(RSI)')
    parser.add_argument('symbol', nargs='?', default=None, help='交易对 (如 BTCUSDT)')
    parser.add_argument('--all', action='store_true', help=f'批量回测 {len(MAINSTREAM_SYMBOLS)} 只主流币')
    parser.add_argument('--top', type=int, default=0, help='只显示前N名 (默认全部)')
    parser.add_argument('--interval', '-i', default='1d', help='K线周期 (默认 1d)')
    parser.add_argument('--days', type=int, default=365, help='回测天数 (默认 365)')
    parser.add_argument('--capital', type=float, default=10000, help='初始资金 (默认 10000)')
    # MA 策略参数
    parser.add_argument('--fast', type=int, default=7, help='快线周期 (默认 7)')
    parser.add_argument('--slow', type=int, default=25, help='慢线周期 (默认 25)')
    # RSI 策略参数
    parser.add_argument('--rsi-period', type=int, default=14, help='RSI周期 (默认 14)')
    parser.add_argument('--oversold', type=int, default=30, help='超卖线 (默认 30)')
    parser.add_argument('--overbought', type=int, default=70, help='超买线 (默认 70)')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    # 批量回测
    if getattr(args, 'all'):
        output = backtest_all(
            args.strategy, args.interval, args.days, args.capital,
            fast=args.fast, slow=args.slow,
            rsi_period=args.rsi_period, oversold=args.oversold,
            overbought=args.overbought, top=args.top
        )
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"\n已保存至: {args.output}")
        return

    if not args.symbol:
        parser.error("请指定交易对 (如 BTCUSDT) 或使用 --all 批量回测")

    symbol = args.symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'

    # 获取 K 线
    df = get_kline(symbol, args.interval, args.days)
    if df is None or len(df) == 0:
        print(f"获取 {symbol} K线数据失败")
        sys.exit(1)

    # 执行回测
    if args.strategy == 'ma':
        result = backtest_ma(df, fast=args.fast, slow=args.slow, initial_capital=args.capital)
    elif args.strategy == 'rsi':
        result = backtest_rsi(df, period=args.rsi_period,
                              oversold=args.oversold, overbought=args.overbought,
                              initial_capital=args.capital)

    # 输出
    output = format_result(result, symbol)
    print(output)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n已保存至: {args.output}")


if __name__ == '__main__':
    main()
