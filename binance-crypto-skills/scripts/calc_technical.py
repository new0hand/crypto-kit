# -*- coding: utf-8 -*-
"""
加密货币技术指标计算

支持指标:
- MA: 均线 (7/25/99日，加密货币常用)
- MACD: 指数平滑异同移动平均线
- RSI: 相对强弱指标
- KDJ: 随机指标
- BOLL: 布林带

用法:
    python calc_technical.py BTCUSDT
    python calc_technical.py ETHUSDT --interval 4h --days 90
    python calc_technical.py BTCUSDT --indicators MA MACD RSI
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

# 导入 K 线获取
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from get_kline import get_kline


def calc_ma(df: pd.DataFrame, periods: list = [7, 25, 99]) -> pd.DataFrame:
    """计算均线（加密货币常用 7/25/99）"""
    for period in periods:
        df[f'MA{period}'] = df['close'].rolling(window=period).mean()
    return df


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """计算 MACD"""
    exp1 = df['close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
    df['MACD'] = 2 * (df['DIF'] - df['DEA'])
    return df


def calc_rsi(df: pd.DataFrame, periods: list = [6, 12, 24]) -> pd.DataFrame:
    """计算 RSI"""
    delta = df['close'].diff()
    for period in periods:
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df[f'RSI{period}'] = 100 - (100 / (1 + rs))
    return df


def calc_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """计算 KDJ"""
    low_min = df['low'].rolling(window=n).min()
    high_max = df['high'].rolling(window=n).max()
    rsv = (df['close'] - low_min) / (high_max - low_min) * 100
    df['K'] = rsv.ewm(alpha=1/m1, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/m2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    return df


def calc_boll(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    """计算布林带"""
    df['BOLL_MID'] = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    df['BOLL_UP'] = df['BOLL_MID'] + std_dev * std
    df['BOLL_DOWN'] = df['BOLL_MID'] - std_dev * std
    return df


def calc_volume_ratio(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
    """计算量比"""
    df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=period).mean()
    return df


def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有技术指标"""
    df = calc_ma(df)
    df = calc_macd(df)
    df = calc_rsi(df)
    df = calc_kdj(df)
    df = calc_boll(df)
    df = calc_volume_ratio(df)
    return df


def analyze_signals(df: pd.DataFrame) -> dict:
    """分析技术信号"""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    signals = {}

    # 均线分析
    if 'MA7' in df.columns and 'MA25' in df.columns:
        if latest['MA7'] > latest['MA25'] and prev['MA7'] <= prev['MA25']:
            signals['均线'] = '🟢 金叉（MA7上穿MA25）'
        elif latest['MA7'] < latest['MA25'] and prev['MA7'] >= prev['MA25']:
            signals['均线'] = '🔴 死叉（MA7下穿MA25）'
        elif latest['close'] > latest['MA7'] > latest['MA25']:
            signals['均线'] = '🟢 多头排列'
        elif latest['close'] < latest['MA7'] < latest['MA25']:
            signals['均线'] = '🔴 空头排列'
        else:
            signals['均线'] = '⚪ 震荡'

    # MACD分析
    if 'DIF' in df.columns and 'DEA' in df.columns:
        if latest['DIF'] > latest['DEA'] and prev['DIF'] <= prev['DEA']:
            signals['MACD'] = '🟢 金叉'
        elif latest['DIF'] < latest['DEA'] and prev['DIF'] >= prev['DEA']:
            signals['MACD'] = '🔴 死叉'
        elif latest['MACD'] > 0:
            signals['MACD'] = '🟢 多头'
        else:
            signals['MACD'] = '🔴 空头'

    # RSI分析
    if 'RSI6' in df.columns:
        rsi = latest['RSI6']
        if rsi > 80:
            signals['RSI'] = f'🔴 超买 ({rsi:.1f})'
        elif rsi < 20:
            signals['RSI'] = f'🟢 超卖 ({rsi:.1f})'
        elif rsi > 50:
            signals['RSI'] = f'🟢 偏强 ({rsi:.1f})'
        else:
            signals['RSI'] = f'🔴 偏弱 ({rsi:.1f})'

    # KDJ分析
    if 'K' in df.columns and 'D' in df.columns:
        if latest['K'] > latest['D'] and prev['K'] <= prev['D'] and latest['K'] < 20:
            signals['KDJ'] = '🟢 低位金叉'
        elif latest['K'] < latest['D'] and prev['K'] >= prev['D'] and latest['K'] > 80:
            signals['KDJ'] = '🔴 高位死叉'
        elif latest['J'] > 100:
            signals['KDJ'] = f'🔴 超买 (J={latest["J"]:.1f})'
        elif latest['J'] < 0:
            signals['KDJ'] = f'🟢 超卖 (J={latest["J"]:.1f})'
        else:
            signals['KDJ'] = '⚪ 中性'

    # 布林带分析
    if 'BOLL_UP' in df.columns:
        if latest['close'] > latest['BOLL_UP']:
            signals['BOLL'] = '🔴 突破上轨（注意回调）'
        elif latest['close'] < latest['BOLL_DOWN']:
            signals['BOLL'] = '🟢 突破下轨（注意反弹）'
        else:
            width = (latest['BOLL_UP'] - latest['BOLL_DOWN']) / latest['BOLL_MID'] * 100
            signals['BOLL'] = f'⚪ 通道内 (带宽{width:.1f}%)'

    return signals


def format_output(df: pd.DataFrame, symbol: str, signals: dict) -> str:
    """格式化输出为 Markdown"""
    latest = df.iloc[-1]

    lines = [
        f"# {symbol} 技术分析\n",
        f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**最新价格**: ${latest['close']:,.2f}\n",
    ]

    # 信号汇总
    lines.append("## 技术信号\n")
    lines.append("| 指标 | 信号 |")
    lines.append("|------|------|")
    for name, signal in signals.items():
        lines.append(f"| {name} | {signal} |")
    lines.append("")

    # 指标数值
    lines.append("## 指标数值\n")

    lines.append("### 均线")
    lines.append("| MA7 | MA25 | MA99 |")
    lines.append("|-----|------|------|")
    ma_vals = []
    for p in [7, 25, 99]:
        v = latest.get(f'MA{p}')
        ma_vals.append(f"${v:,.2f}" if pd.notna(v) else 'N/A')
    lines.append(f"| {' | '.join(ma_vals)} |")
    lines.append("")

    lines.append("### MACD")
    lines.append("| DIF | DEA | MACD |")
    lines.append("|-----|-----|------|")
    dif = f"{latest.get('DIF', 0):,.2f}" if pd.notna(latest.get('DIF')) else 'N/A'
    dea = f"{latest.get('DEA', 0):,.2f}" if pd.notna(latest.get('DEA')) else 'N/A'
    macd = f"{latest.get('MACD', 0):,.2f}" if pd.notna(latest.get('MACD')) else 'N/A'
    lines.append(f"| {dif} | {dea} | {macd} |")
    lines.append("")

    lines.append("### RSI")
    lines.append("| RSI6 | RSI12 | RSI24 |")
    lines.append("|------|-------|-------|")
    rsi_vals = [f"{latest.get(f'RSI{p}', 0):.2f}" if pd.notna(latest.get(f'RSI{p}')) else 'N/A' for p in [6, 12, 24]]
    lines.append(f"| {' | '.join(rsi_vals)} |")
    lines.append("")

    lines.append("### KDJ")
    lines.append("| K | D | J |")
    lines.append("|---|---|---|")
    kdj_vals = [f"{latest.get(k, 0):.2f}" if pd.notna(latest.get(k)) else 'N/A' for k in ['K', 'D', 'J']]
    lines.append(f"| {' | '.join(kdj_vals)} |")
    lines.append("")

    lines.append("### 布林带")
    lines.append("| 上轨 | 中轨 | 下轨 |")
    lines.append("|------|------|------|")
    boll_vals = [f"${latest.get(k, 0):,.2f}" if pd.notna(latest.get(k)) else 'N/A' for k in ['BOLL_UP', 'BOLL_MID', 'BOLL_DOWN']]
    lines.append(f"| {' | '.join(boll_vals)} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='计算加密货币技术指标')
    parser.add_argument('symbol', help='交易对 (如 BTCUSDT)')
    parser.add_argument('--interval', '-i', default='1d', help='K线周期 (默认 1d)')
    parser.add_argument('--days', type=int, default=120, help='计算周期天数')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    symbol = args.symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'

    # 获取 K 线
    df = get_kline(symbol, args.interval, args.days)

    if df is None or len(df) == 0:
        print(f"获取 {symbol} K线数据失败")
        sys.exit(1)

    # 计算指标
    df = calc_all_indicators(df)

    # 分析信号
    signals = analyze_signals(df)

    # 输出
    output = format_output(df, symbol, signals)
    print(output)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n已保存至: {args.output}")


if __name__ == '__main__':
    main()
