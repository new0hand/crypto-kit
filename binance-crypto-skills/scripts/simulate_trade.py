# -*- coding: utf-8 -*-
"""
模拟交易（Paper Trading）

基于实时 K 线数据进行纸上交易，不需要 API Key，不涉及真实资金。
交易记录保存在本地 JSON 文件中。

用法:
    python simulate_trade.py buy BTCUSDT 0.01              # 买入 0.01 BTC
    python simulate_trade.py buy BTCUSDT --usdt 500         # 用 500 USDT 买入
    python simulate_trade.py sell BTCUSDT 0.01              # 卖出 0.01 BTC
    python simulate_trade.py sell BTCUSDT --all              # 全部卖出
    python simulate_trade.py status                          # 查看账户状态
    python simulate_trade.py history                         # 查看交易历史
    python simulate_trade.py reset                           # 重置账户
    python simulate_trade.py reset --capital 50000           # 重置并设初始资金
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

DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
ACCOUNT_FILE = os.path.join(DATA_DIR, "simulate_account.json")

# 默认初始资金
DEFAULT_CAPITAL = 10000.0

# 交易手续费（币安现货 0.1%，VIP 更低）
FEE_RATE = 0.001


def get_price(symbol: str) -> float:
    """获取最新价格"""
    try:
        resp = spot_get("/api/v3/ticker/price", params={"symbol": symbol.upper()})
        resp.raise_for_status()
        return float(resp.json()['price'])
    except Exception as e:
        print(f"获取 {symbol} 价格失败: {e}")
        return None


def load_account() -> dict:
    """加载账户数据"""
    if os.path.exists(ACCOUNT_FILE):
        with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    return {
        'usdt_balance': DEFAULT_CAPITAL,
        'initial_capital': DEFAULT_CAPITAL,
        'positions': {},  # {symbol: amount}
        'trades': [],
        'created_at': datetime.now().isoformat(),
    }


def save_account(account: dict):
    """保存账户数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        json.dump(account, f, ensure_ascii=False, indent=2)


def do_buy(account: dict, symbol: str, amount: float = None, usdt_amount: float = None) -> str:
    """执行买入"""
    symbol = symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'

    price = get_price(symbol)
    if price is None:
        return f"获取 {symbol} 价格失败，无法交易"

    if usdt_amount:
        # 按 USDT 金额买入
        fee = usdt_amount * FEE_RATE
        actual_usdt = usdt_amount - fee
        amount = actual_usdt / price
    elif amount:
        usdt_amount = amount * price
        fee = usdt_amount * FEE_RATE
        usdt_amount += fee
    else:
        return "请指定买入数量或 USDT 金额"

    if usdt_amount > account['usdt_balance']:
        return f"余额不足。需要 ${usdt_amount:,.2f}，当前余额 ${account['usdt_balance']:,.2f}"

    # 扣款
    account['usdt_balance'] -= usdt_amount

    # 加仓
    base = symbol.replace('USDT', '')
    if base not in account['positions']:
        account['positions'][base] = 0
    account['positions'][base] += amount

    # 记录交易
    trade = {
        'type': 'BUY',
        'symbol': symbol,
        'price': price,
        'amount': amount,
        'usdt': usdt_amount,
        'fee': fee if usdt_amount else amount * price * FEE_RATE,
        'time': datetime.now().isoformat(),
    }
    account['trades'].append(trade)
    save_account(account)

    return (
        f"🟢 买入成功\n"
        f"交易对: {symbol}\n"
        f"价格: ${price:,.2f}\n"
        f"数量: {amount:.6f} {base}\n"
        f"花费: ${usdt_amount:,.2f} (含手续费 ${fee:,.2f})\n"
        f"剩余余额: ${account['usdt_balance']:,.2f}"
    )


def do_sell(account: dict, symbol: str, amount: float = None, sell_all: bool = False) -> str:
    """执行卖出"""
    symbol = symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
    base = symbol.replace('USDT', '')

    held = account['positions'].get(base, 0)
    if held <= 0:
        return f"未持有 {base}"

    if sell_all:
        amount = held
    elif amount is None:
        return "请指定卖出数量或使用 --all"
    elif amount > held:
        return f"持仓不足。持有 {held:.6f} {base}，卖出 {amount:.6f}"

    price = get_price(symbol)
    if price is None:
        return f"获取 {symbol} 价格失败，无法交易"

    usdt_received = amount * price
    fee = usdt_received * FEE_RATE
    usdt_received -= fee

    # 加款
    account['usdt_balance'] += usdt_received

    # 减仓
    account['positions'][base] -= amount
    if account['positions'][base] <= 1e-10:
        del account['positions'][base]

    trade = {
        'type': 'SELL',
        'symbol': symbol,
        'price': price,
        'amount': amount,
        'usdt': usdt_received,
        'fee': fee,
        'time': datetime.now().isoformat(),
    }
    account['trades'].append(trade)
    save_account(account)

    return (
        f"🔴 卖出成功\n"
        f"交易对: {symbol}\n"
        f"价格: ${price:,.2f}\n"
        f"数量: {amount:.6f} {base}\n"
        f"收入: ${usdt_received:,.2f} (扣手续费 ${fee:,.2f})\n"
        f"当前余额: ${account['usdt_balance']:,.2f}"
    )


def show_status(account: dict) -> str:
    """显示账户状态"""
    lines = [
        "# 模拟账户状态\n",
        f"**初始资金**: ${account['initial_capital']:,.2f}",
        f"**USDT余额**: ${account['usdt_balance']:,.2f}",
        f"**交易次数**: {len(account['trades'])}\n",
    ]

    # 持仓
    total_value = account['usdt_balance']

    if account['positions']:
        lines.append("## 当前持仓\n")
        lines.append("| 币种 | 数量 | 现价 | 市值 |")
        lines.append("|------|------|------|------|")

        for base, amount in account['positions'].items():
            symbol = f"{base}USDT"
            price = get_price(symbol)
            if price:
                value = amount * price
                total_value += value
                lines.append(f"| {base} | {amount:.6f} | ${price:,.2f} | ${value:,.2f} |")
            else:
                lines.append(f"| {base} | {amount:.6f} | N/A | N/A |")

        lines.append("")

    # 总结
    pnl = total_value - account['initial_capital']
    pnl_pct = pnl / account['initial_capital'] * 100
    trend = "🟢" if pnl >= 0 else "🔴"

    lines.extend([
        "## 账户总结\n",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总资产 | ${total_value:,.2f} |",
        f"| 盈亏 | {trend} ${pnl:+,.2f} ({pnl_pct:+.2f}%) |",
    ])

    return "\n".join(lines)


def show_history(account: dict, limit: int = 20) -> str:
    """显示交易历史"""
    trades = account['trades']
    if not trades:
        return "暂无交易记录"

    lines = [
        f"# 交易历史 (共 {len(trades)} 笔)\n",
        "| 时间 | 操作 | 交易对 | 价格 | 数量 | USDT |",
        "|------|------|--------|------|------|------|",
    ]

    for t in trades[-limit:]:
        dt = t['time'][:16].replace('T', ' ')
        icon = "🟢买入" if t['type'] == 'BUY' else "🔴卖出"
        lines.append(
            f"| {dt} | {icon} | {t['symbol']} | ${t['price']:,.2f} | "
            f"{t['amount']:.6f} | ${t['usdt']:,.2f} |"
        )

    if len(trades) > limit:
        lines.append(f"\n> 仅显示最近 {limit} 笔")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='模拟交易')
    subparsers = parser.add_subparsers(dest='action', help='操作')

    # 买入
    buy_parser = subparsers.add_parser('buy', help='买入')
    buy_parser.add_argument('symbol', help='交易对')
    buy_parser.add_argument('amount', nargs='?', type=float, help='买入数量')
    buy_parser.add_argument('--usdt', type=float, help='按 USDT 金额买入')

    # 卖出
    sell_parser = subparsers.add_parser('sell', help='卖出')
    sell_parser.add_argument('symbol', help='交易对')
    sell_parser.add_argument('amount', nargs='?', type=float, help='卖出数量')
    sell_parser.add_argument('--all', action='store_true', help='全部卖出')

    # 状态
    subparsers.add_parser('status', help='账户状态')

    # 历史
    hist_parser = subparsers.add_parser('history', help='交易历史')
    hist_parser.add_argument('--limit', type=int, default=20, help='显示条数')

    # 重置
    reset_parser = subparsers.add_parser('reset', help='重置账户')
    reset_parser.add_argument('--capital', type=float, default=DEFAULT_CAPITAL, help='初始资金')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return

    account = load_account()

    if args.action == 'buy':
        print(do_buy(account, args.symbol, args.amount, args.usdt))

    elif args.action == 'sell':
        print(do_sell(account, args.symbol, args.amount, args.all))

    elif args.action == 'status':
        print(show_status(account))

    elif args.action == 'history':
        print(show_history(account, args.limit))

    elif args.action == 'reset':
        account = {
            'usdt_balance': args.capital,
            'initial_capital': args.capital,
            'positions': {},
            'trades': [],
            'created_at': datetime.now().isoformat(),
        }
        save_account(account)
        print(f"账户已重置，初始资金: ${args.capital:,.2f}")


if __name__ == '__main__':
    main()
