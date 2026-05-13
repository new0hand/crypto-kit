# -*- coding: utf-8 -*-
"""
批量下载币安历史 K 线数据，保存为 Parquet 格式

支持增量更新，只拉取缺失的部分。

用法:
    python download_history.py                            # 下载 BTC/ETH 日线（默认2年）
    python download_history.py --symbols BTCUSDT ETHUSDT SOLUSDT
    python download_history.py --interval 1h --days 90    # 下载1小时线
    python download_history.py --update                   # 增量更新
    python download_history.py --summary                  # 查看数据摘要
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
    print("请先安装依赖: pip install pandas requests pyarrow")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SCRIPT_DIR, "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)
from api_client import spot_get, futures_get
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")

# 默认下载的交易对
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# 默认下载的周期
DEFAULT_INTERVALS = ["1d"]


def fetch_klines(symbol: str, interval: str, start_ts: int, end_ts: int,
                 futures: bool = False, limit: int = 1000) -> list:
    """从 API 获取 K 线原始数据"""
    api_func = futures_get if futures else spot_get
    path = "/fapi/v1/klines" if futures else "/api/v3/klines"

    all_data = []
    current = start_ts

    while current < end_ts:
        params = {
            "symbol": symbol, "interval": interval,
            "startTime": current, "endTime": end_ts, "limit": limit
        }

        try:
            resp = api_func(path, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_data.extend(data)

            last_ts = data[-1][0]
            if last_ts == current:
                break
            current = last_ts + 1

            if len(data) < limit:
                break

            time.sleep(0.1)
        except Exception as e:
            print(f"  请求失败: {e}")
            time.sleep(1)
            continue

    return all_data


def raw_to_df(raw_data: list) -> pd.DataFrame:
    """原始数据转 DataFrame"""
    df = pd.DataFrame(raw_data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
        'taker_buy_quote_volume', 'ignore'
    ])

    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume',
                'taker_buy_volume', 'taker_buy_quote_volume']:
        df[col] = df[col].astype(float)
    df['open_time'] = df['open_time'].astype(int)
    df['close_time'] = df['close_time'].astype(int)
    df['trades'] = df['trades'].astype(int)
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

    df = df.drop(columns=['ignore'])
    df = df.drop_duplicates(subset=['open_time']).sort_values('open_time').reset_index(drop=True)
    return df


def download_symbol(symbol: str, interval: str, days: int,
                    futures: bool = False, update: bool = False) -> str:
    """下载单个交易对"""
    os.makedirs(DATA_DIR, exist_ok=True)
    prefix = "futures_" if futures else ""
    parquet_file = os.path.join(DATA_DIR, f"{prefix}{symbol}_{interval}.parquet")

    end_ts = int(datetime.now().timestamp() * 1000)

    if update and os.path.exists(parquet_file):
        # 增量更新：从最后一条数据开始
        existing = pd.read_parquet(parquet_file)
        start_ts = int(existing['open_time'].max()) + 1
        print(f"  增量更新: {symbol} {interval} (从 {datetime.fromtimestamp(start_ts/1000).strftime('%Y-%m-%d')})")
    else:
        start_ts = end_ts - (days * 24 * 60 * 60 * 1000)
        existing = None
        print(f"  全量下载: {symbol} {interval} (最近 {days} 天)")

    if start_ts >= end_ts:
        print(f"  {symbol} 已是最新")
        return "已是最新"

    raw = fetch_klines(symbol, interval, start_ts, end_ts, futures=futures)
    if not raw:
        print(f"  {symbol} 无新数据")
        return "无新数据"

    new_df = raw_to_df(raw)

    # 合并旧数据
    if existing is not None and len(existing) > 0:
        df = pd.concat([existing, new_df]).drop_duplicates(subset=['open_time']).sort_values('open_time').reset_index(drop=True)
    else:
        df = new_df

    # 保存
    df.to_parquet(parquet_file, index=False)
    size_mb = os.path.getsize(parquet_file) / 1024 / 1024

    msg = f"  保存: {parquet_file} ({len(df)} 条, {size_mb:.2f}MB)"
    print(msg)
    return msg


def show_summary():
    """显示数据摘要"""
    if not os.path.exists(DATA_DIR):
        print("数据目录为空")
        return

    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.parquet')]
    if not files:
        print("无 Parquet 数据文件")
        return

    print("# 数据摘要\n")
    print("| 文件 | 条数 | 起始日期 | 结束日期 | 大小 |")
    print("|------|------|----------|----------|------|")

    for f in sorted(files):
        path = os.path.join(DATA_DIR, f)
        try:
            df = pd.read_parquet(path)
            start = pd.to_datetime(df['open_time'].min(), unit='ms').strftime('%Y-%m-%d')
            end = pd.to_datetime(df['open_time'].max(), unit='ms').strftime('%Y-%m-%d')
            size = os.path.getsize(path) / 1024 / 1024
            print(f"| {f} | {len(df)} | {start} | {end} | {size:.2f}MB |")
        except Exception as e:
            print(f"| {f} | 错误: {e} | | | |")


def main():
    parser = argparse.ArgumentParser(description='下载币安历史K线数据')
    parser.add_argument('--symbols', nargs='+', default=DEFAULT_SYMBOLS, help='交易对列表')
    parser.add_argument('--interval', '-i', default='1d', help='K线周期 (默认 1d)')
    parser.add_argument('--days', type=int, default=730, help='下载天数 (默认 730)')
    parser.add_argument('--futures', action='store_true', help='下载合约数据')
    parser.add_argument('--update', action='store_true', help='增量更新')
    parser.add_argument('--summary', action='store_true', help='查看数据摘要')

    args = parser.parse_args()

    if args.summary:
        show_summary()
        return

    print(f"下载币安 K 线数据")
    print(f"交易对: {', '.join(args.symbols)}")
    print(f"周期: {args.interval}")
    print(f"模式: {'增量更新' if args.update else f'全量 {args.days} 天'}")
    print(f"类型: {'合约' if args.futures else '现货'}")
    print("-" * 40)

    for symbol in args.symbols:
        symbol = symbol.upper()
        download_symbol(symbol, args.interval, args.days,
                        futures=args.futures, update=args.update)

    print("\n完成!")
    show_summary()


if __name__ == '__main__':
    main()
