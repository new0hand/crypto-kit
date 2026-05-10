# -*- coding: utf-8 -*-
"""
获取加密货币实时行情

使用币安公开 API，无需 API Key。

用法:
    python get_realtime.py BTCUSDT
    python get_realtime.py ETHUSDT
    python get_realtime.py BTCUSDT ETHUSDT SOLUSDT   # 多币种
    python get_realtime.py --all                      # 主流币种概览
"""
import argparse
import json
import os
import sys
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import requests
except ImportError:
    print("请先安装依赖: pip install requests")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from api_client import spot_get

# 主流交易对
POPULAR_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"
]


def get_ticker_24h(symbol: str) -> dict:
    """获取 24 小时行情统计"""
    try:
        resp = spot_get("/api/v3/ticker/24hr", params={"symbol": symbol.upper()})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"获取 {symbol} 行情失败: {e}")
        return None


def get_ticker_price(symbol: str) -> dict:
    """获取最新价格"""
    try:
        resp = spot_get("/api/v3/ticker/price", params={"symbol": symbol.upper()})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"获取 {symbol} 价格失败: {e}")
        return None


def get_orderbook(symbol: str, limit: int = 5) -> dict:
    """获取盘口深度"""
    try:
        resp = spot_get("/api/v3/depth", params={"symbol": symbol.upper(), "limit": limit})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"获取 {symbol} 盘口失败: {e}")
        return None


def format_number(num, decimals=2):
    """格式化数字"""
    try:
        n = float(num)
        if abs(n) >= 1e9:
            return f"{n/1e9:.{decimals}f}B"
        elif abs(n) >= 1e6:
            return f"{n/1e6:.{decimals}f}M"
        elif abs(n) >= 1e3:
            return f"{n/1e3:.{decimals}f}K"
        else:
            return f"{n:.{decimals}f}"
    except (ValueError, TypeError):
        return str(num)


def format_single(ticker: dict, symbol: str) -> str:
    """格式化单个币种行情"""
    if not ticker:
        return f"获取 {symbol} 行情失败"

    price = float(ticker.get('lastPrice', 0))
    change_pct = float(ticker.get('priceChangePercent', 0))
    high = float(ticker.get('highPrice', 0))
    low = float(ticker.get('lowPrice', 0))
    volume = float(ticker.get('volume', 0))
    quote_volume = float(ticker.get('quoteVolume', 0))
    open_price = float(ticker.get('openPrice', 0))
    count = int(ticker.get('count', 0))

    # 涨跌标识
    trend = "🟢" if change_pct >= 0 else "🔴"

    lines = [
        f"# {symbol} 实时行情\n",
        f"**查询时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 最新价 | ${price:,.2f} |",
        f"| 24h涨跌 | {trend} {change_pct:+.2f}% |",
        f"| 24h最高 | ${high:,.2f} |",
        f"| 24h最低 | ${low:,.2f} |",
        f"| 24h开盘 | ${open_price:,.2f} |",
        f"| 24h成交量 | {format_number(volume)} |",
        f"| 24h成交额 | ${format_number(quote_volume)} |",
        f"| 24h成交笔数 | {format_number(count)} |",
    ]

    return "\n".join(lines)


def format_overview(tickers: list) -> str:
    """格式化多币种概览"""
    lines = [
        "# 主流加密货币行情概览\n",
        f"**查询时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "| 币种 | 最新价 | 24h涨跌 | 24h成交额 |",
        "|------|--------|---------|-----------|",
    ]

    for t in tickers:
        if not t:
            continue
        symbol = t.get('symbol', '')
        price = float(t.get('lastPrice', 0))
        change = float(t.get('priceChangePercent', 0))
        vol = float(t.get('quoteVolume', 0))
        trend = "🟢" if change >= 0 else "🔴"

        # 根据价格大小调整精度
        if price >= 100:
            price_str = f"${price:,.2f}"
        elif price >= 1:
            price_str = f"${price:.4f}"
        else:
            price_str = f"${price:.6f}"

        lines.append(
            f"| {symbol} | {price_str} | {trend} {change:+.2f}% | ${format_number(vol)} |"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='获取加密货币实时行情')
    parser.add_argument('symbols', nargs='*', help='交易对 (如 BTCUSDT)')
    parser.add_argument('--all', action='store_true', help='显示主流币种概览')
    parser.add_argument('--depth', action='store_true', help='显示盘口深度')

    args = parser.parse_args()

    if args.all or not args.symbols:
        # 主流币种概览 - 一次请求拿全部，本地过滤
        try:
            resp = spot_get("/api/v3/ticker/24hr", timeout=15)
            resp.raise_for_status()
            all_tickers = resp.json()
            # 过滤出主流币种，按 POPULAR_SYMBOLS 顺序排列
            popular_set = set(POPULAR_SYMBOLS)
            order = {s: i for i, s in enumerate(POPULAR_SYMBOLS)}
            tickers = [t for t in all_tickers if t.get('symbol') in popular_set]
            tickers.sort(key=lambda t: order.get(t.get('symbol', ''), 99))
        except Exception:
            # 回退：逐个查询
            tickers = []
            for sym in POPULAR_SYMBOLS:
                t = get_ticker_24h(sym)
                if t:
                    tickers.append(t)
        print(format_overview(tickers))

    else:
        for symbol in args.symbols:
            symbol = symbol.upper()
            if not symbol.endswith('USDT'):
                symbol += 'USDT'

            ticker = get_ticker_24h(symbol)
            print(format_single(ticker, symbol))

            if args.depth:
                book = get_orderbook(symbol)
                if book:
                    print(f"\n## {symbol} 盘口深度\n")
                    print("| 买盘价格 | 买盘数量 | 卖盘价格 | 卖盘数量 |")
                    print("|----------|----------|----------|----------|")
                    bids = book.get('bids', [])[:5]
                    asks = book.get('asks', [])[:5]
                    for i in range(min(len(bids), len(asks))):
                        bp, bq = bids[i][0], bids[i][1]
                        ap, aq = asks[i][0], asks[i][1]
                        print(f"| ${float(bp):,.2f} | {float(bq):.4f} | ${float(ap):,.2f} | {float(aq):.4f} |")

            print()


if __name__ == '__main__':
    main()
