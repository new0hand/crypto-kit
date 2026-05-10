# -*- coding: utf-8 -*-
"""
获取币安合约（期货）K 线数据

使用币安合约公开 API，无需 API Key。
支持 USDT 永续合约和币本位合约。

用法:
    python get_futures_kline.py BTCUSDT
    python get_futures_kline.py ETHUSDT --days 30
    python get_futures_kline.py BTCUSDT --interval 4h --days 90
    python get_futures_kline.py BTCUSDT --funding    # 查看资金费率
    python get_futures_kline.py BTCUSDT --oi         # 查看持仓量
"""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import pandas as pd
    import requests
except ImportError:
    print("请先安装依赖: pip install pandas requests")
    sys.exit(1)

SCRIPT_DIR_FUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR_FUT)
from api_client import futures_get


def get_futures_kline_api(symbol: str, interval: str, start_ts: int, end_ts: int,
                          limit_per_request: int = 1500) -> pd.DataFrame:
    """从币安合约 API 获取 K 线数据"""
    all_data = []
    current_start = start_ts

    while current_start < end_ts:
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ts,
            "limit": limit_per_request
        }

        try:
            resp = futures_get("/fapi/v1/klines", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            all_data.extend(data)

            last_open_time = data[-1][0]
            if last_open_time == current_start:
                break
            current_start = last_open_time + 1

            if len(data) < limit_per_request:
                break

            time.sleep(0.1)

        except Exception as e:
            print(f"  API 请求失败: {e}")
            break

    if not all_data:
        return None

    df = pd.DataFrame(all_data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
        'taker_buy_quote_volume', 'ignore'
    ])

    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
        df[col] = df[col].astype(float)
    df['open_time'] = df['open_time'].astype(int)
    df['close_time'] = df['close_time'].astype(int)
    df['trades'] = df['trades'].astype(int)
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

    df = df.drop_duplicates(subset=['open_time']).sort_values('open_time').reset_index(drop=True)
    return df


def get_funding_rate(symbol: str, limit: int = 30) -> pd.DataFrame:
    """获取资金费率历史"""
    params = {"symbol": symbol.upper(), "limit": limit}

    try:
        resp = futures_get("/fapi/v1/fundingRate", params=params)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            return None

        df = pd.DataFrame(data)
        df['fundingRate'] = df['fundingRate'].astype(float)
        df['datetime'] = pd.to_datetime(df['fundingTime'], unit='ms')
        df = df.sort_values('fundingTime').reset_index(drop=True)
        return df

    except Exception as e:
        print(f"获取资金费率失败: {e}")
        return None


def get_open_interest(symbol: str) -> dict:
    """获取当前持仓量"""
    params = {"symbol": symbol.upper()}

    try:
        resp = futures_get("/fapi/v1/openInterest", params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"获取持仓量失败: {e}")
        return None


def get_open_interest_hist(symbol: str, period: str = '5m', limit: int = 30) -> pd.DataFrame:
    """获取持仓量历史"""
    params = {"symbol": symbol.upper(), "period": period, "limit": limit}

    try:
        resp = futures_get("/futures/data/openInterestHist", params=params)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            return None

        df = pd.DataFrame(data)
        df['sumOpenInterest'] = df['sumOpenInterest'].astype(float)
        df['sumOpenInterestValue'] = df['sumOpenInterestValue'].astype(float)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    except Exception as e:
        print(f"获取持仓量历史失败: {e}")
        return None


def format_kline(df: pd.DataFrame, symbol: str) -> str:
    """格式化 K 线输出"""
    lines = [
        f"# {symbol} 合约 K线数据\n",
        f"**数据范围**: {df['datetime'].iloc[0].strftime('%Y-%m-%d')} ~ {df['datetime'].iloc[-1].strftime('%Y-%m-%d')}",
        f"**数据条数**: {len(df)}\n",
        "## 最近 10 条\n",
        "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量 |",
        "|------|------|------|------|------|--------|",
    ]

    for _, row in df.tail(10).iterrows():
        dt = row['datetime'].strftime('%Y-%m-%d %H:%M')
        lines.append(
            f"| {dt} | {row['open']:,.2f} | {row['high']:,.2f} | "
            f"{row['low']:,.2f} | {row['close']:,.2f} | {row['volume']:,.2f} |"
        )

    return "\n".join(lines)


def format_funding(df: pd.DataFrame, symbol: str) -> str:
    """格式化资金费率输出"""
    lines = [
        f"# {symbol} 资金费率历史\n",
        f"**最新费率**: {df['fundingRate'].iloc[-1]*100:.4f}%",
        f"**平均费率**: {df['fundingRate'].mean()*100:.4f}%\n",
        "| 时间 | 费率 | 年化 |",
        "|------|------|------|",
    ]

    for _, row in df.tail(20).iterrows():
        dt = row['datetime'].strftime('%Y-%m-%d %H:%M')
        rate = row['fundingRate']
        annual = rate * 3 * 365 * 100  # 每 8 小时一次，年化
        trend = "🟢" if rate >= 0 else "🔴"
        lines.append(f"| {dt} | {trend} {rate*100:.4f}% | {annual:.1f}% |")

    return "\n".join(lines)


def format_oi(oi: dict, oi_hist: pd.DataFrame, symbol: str) -> str:
    """格式化持仓量输出"""
    lines = [f"# {symbol} 合约持仓量\n"]

    if oi:
        oi_val = float(oi.get('openInterest', 0))
        lines.append(f"**当前持仓**: {oi_val:,.2f} {symbol.replace('USDT', '')}\n")

    if oi_hist is not None and len(oi_hist) > 0:
        lines.extend([
            "## 持仓量变化\n",
            "| 时间 | 持仓量(币) | 持仓价值(USDT) |",
            "|------|-----------|----------------|",
        ])
        for _, row in oi_hist.tail(20).iterrows():
            dt = row['datetime'].strftime('%Y-%m-%d %H:%M')
            lines.append(
                f"| {dt} | {row['sumOpenInterest']:,.2f} | ${row['sumOpenInterestValue']:,.0f} |"
            )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='获取币安合约K线数据')
    parser.add_argument('symbol', help='交易对 (如 BTCUSDT)')
    parser.add_argument('--interval', '-i', default='1d',
                        help='K线周期: 1m/5m/15m/1h/4h/1d (默认 1d)')
    parser.add_argument('--days', type=int, default=60, help='最近N天')
    parser.add_argument('--start', help='开始日期 YYYYMMDD')
    parser.add_argument('--end', help='结束日期 YYYYMMDD')
    parser.add_argument('--funding', action='store_true', help='查看资金费率')
    parser.add_argument('--oi', action='store_true', help='查看持仓量')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()
    symbol = args.symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'

    output_parts = []

    if args.funding:
        # 资金费率
        df = get_funding_rate(symbol, limit=100)
        if df is not None:
            output_parts.append(format_funding(df, symbol))
        else:
            output_parts.append(f"获取 {symbol} 资金费率失败")

    elif args.oi:
        # 持仓量
        oi = get_open_interest(symbol)
        oi_hist = get_open_interest_hist(symbol, period='1h', limit=48)
        output_parts.append(format_oi(oi, oi_hist, symbol))

    else:
        # K线数据
        end_ts = int(datetime.now().timestamp() * 1000)
        if args.end:
            end_ts = int(datetime.strptime(args.end, '%Y%m%d').timestamp() * 1000)
        if args.start:
            start_ts = int(datetime.strptime(args.start, '%Y%m%d').timestamp() * 1000)
        else:
            start_ts = end_ts - (args.days * 24 * 60 * 60 * 1000)

        print(f"获取合约数据: {symbol} {args.interval}")
        df = get_futures_kline_api(symbol, args.interval, start_ts, end_ts)
        if df is not None:
            print(f"  获取成功: {len(df)} 条记录")
            output_parts.append(format_kline(df, symbol))
        else:
            output_parts.append(f"获取 {symbol} 合约K线失败")

    output = "\n\n".join(output_parts)
    print(output)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n已保存至: {args.output}")


if __name__ == '__main__':
    main()
