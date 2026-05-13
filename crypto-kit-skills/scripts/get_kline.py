# -*- coding: utf-8 -*-
"""
获取现货 K 线数据

使用币安公开 API，无需 API Key。
优先从本地 Parquet 读取，本地无数据时回退到在线 API。

用法:
    python get_kline.py BTCUSDT
    python get_kline.py BTCUSDT --days 60
    python get_kline.py ETHUSDT --interval 1h --days 7
    python get_kline.py BTCUSDT --start 20240101 --end 20241231
    python get_kline.py BTCUSDT --online   # 强制在线获取

支持周期: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from api_client import spot_get
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")

# 周期对应的默认天数
INTERVAL_DEFAULTS = {
    '1m': 1, '3m': 2, '5m': 3, '15m': 7, '30m': 14,
    '1h': 30, '2h': 60, '4h': 90, '6h': 120,
    '8h': 180, '12h': 180, '1d': 365, '3d': 730, '1w': 1095, '1M': 1825
}


def get_from_local(symbol: str, interval: str, start_ts: int, end_ts: int) -> pd.DataFrame:
    """从本地 Parquet 读取"""
    parquet_file = os.path.join(DATA_DIR, f"{symbol.upper()}_{interval}.parquet")
    if not os.path.exists(parquet_file):
        return None

    try:
        df = pd.read_parquet(parquet_file)
        mask = (df['open_time'] >= start_ts) & (df['open_time'] <= end_ts)
        df = df[mask].copy()
        if len(df) > 0:
            return df
    except Exception:
        pass
    return None


def get_from_api(symbol: str, interval: str, start_ts: int, end_ts: int,
                 limit_per_request: int = 1000) -> pd.DataFrame:
    """从币安 API 获取 K 线数据（自动分页）"""
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
            resp = spot_get("/api/v3/klines", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            all_data.extend(data)

            # 下一页起点
            last_open_time = data[-1][0]
            if last_open_time == current_start:
                break
            current_start = last_open_time + 1

            # 已到末尾
            if len(data) < limit_per_request:
                break

            # 控制频率（币安限速 1200 req/min）
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

    # 类型转换
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
        df[col] = df[col].astype(float)
    df['open_time'] = df['open_time'].astype(int)
    df['close_time'] = df['close_time'].astype(int)
    df['trades'] = df['trades'].astype(int)

    # 添加可读日期列
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

    # 去重
    df = df.drop_duplicates(subset=['open_time']).sort_values('open_time').reset_index(drop=True)

    return df


def get_kline(symbol: str, interval: str = '1d', days: int = None,
              start_date: str = None, end_date: str = None,
              force_online: bool = False) -> pd.DataFrame:
    """获取 K 线数据（优先本地，回退在线）"""
    symbol = symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'

    if days is None and start_date is None:
        days = INTERVAL_DEFAULTS.get(interval, 60)

    # 计算时间范围
    end_ts = int(datetime.now().timestamp() * 1000)
    if end_date:
        end_ts = int(datetime.strptime(end_date, '%Y%m%d').timestamp() * 1000)

    if start_date:
        start_ts = int(datetime.strptime(start_date, '%Y%m%d').timestamp() * 1000)
    else:
        start_ts = end_ts - (days * 24 * 60 * 60 * 1000)

    print(f"获取数据: {symbol} {interval} ({datetime.fromtimestamp(start_ts/1000).strftime('%Y-%m-%d')} ~ {datetime.fromtimestamp(end_ts/1000).strftime('%Y-%m-%d')})")

    # 优先本地数据
    if not force_online:
        df = get_from_local(symbol, interval, start_ts, end_ts)
        if df is not None and len(df) > 0:
            print(f"  从本地数据加载: {len(df)} 条记录")
            return df

    # 在线获取
    print("  从币安 API 获取...")
    df = get_from_api(symbol, interval, start_ts, end_ts)
    if df is not None and len(df) > 0:
        print(f"  获取成功: {len(df)} 条记录")
        return df

    print("  获取失败")
    return None


def format_output(df: pd.DataFrame, symbol: str) -> str:
    """格式化输出"""
    lines = [
        f"# {symbol} K线数据\n",
        f"**数据范围**: {df['datetime'].iloc[0].strftime('%Y-%m-%d')} ~ {df['datetime'].iloc[-1].strftime('%Y-%m-%d')}",
        f"**数据条数**: {len(df)}\n",
        "## 最近 10 条\n",
        "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量 |",
        "|------|------|------|------|------|--------|",
    ]

    for _, row in df.tail(10).iterrows():
        dt = row['datetime'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['datetime']) else ''
        lines.append(
            f"| {dt} | {row['open']:,.2f} | {row['high']:,.2f} | "
            f"{row['low']:,.2f} | {row['close']:,.2f} | {row['volume']:,.2f} |"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='获取加密货币现货K线数据')
    parser.add_argument('symbol', help='交易对 (如 BTCUSDT, ETH)')
    parser.add_argument('--interval', '-i', default='1d',
                        help='K线周期: 1m/5m/15m/30m/1h/4h/1d/1w (默认 1d)')
    parser.add_argument('--days', type=int, help='最近N天')
    parser.add_argument('--start', help='开始日期 YYYYMMDD')
    parser.add_argument('--end', help='结束日期 YYYYMMDD')
    parser.add_argument('--online', action='store_true', help='强制在线获取')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    df = get_kline(
        args.symbol, args.interval, args.days,
        args.start, args.end, args.online
    )

    if df is not None:
        symbol = args.symbol.upper()
        if not symbol.endswith('USDT'):
            symbol += 'USDT'
        output = format_output(df, symbol)
        print(output)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"\n已保存至: {args.output}")


if __name__ == '__main__':
    main()
