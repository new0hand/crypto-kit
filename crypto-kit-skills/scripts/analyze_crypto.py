# -*- coding: utf-8 -*-
"""
加密货币综合分析

综合技术面、资金费率、持仓量进行多维度分析

用法:
    python analyze_crypto.py BTCUSDT
    python analyze_crypto.py ETHUSDT -o report.md
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
    import requests
except ImportError:
    print("请先安装依赖: pip install pandas numpy requests")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from get_kline import get_kline
from get_realtime import get_ticker_24h
from get_futures_kline import get_funding_rate, get_open_interest, get_open_interest_hist
from calc_technical import calc_all_indicators, analyze_signals


class CryptoAnalyzer:
    """加密货币综合分析器"""

    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        if not self.symbol.endswith('USDT'):
            self.symbol += 'USDT'
        self.base = self.symbol.replace('USDT', '')
        self.data = {}
        self.analysis = {}

    def fetch_data(self):
        """获取所有需要的数据"""
        # 24h 行情
        try:
            self.data['ticker'] = get_ticker_24h(self.symbol)
        except Exception:
            pass

        # 日 K 线
        try:
            self.data['kline'] = get_kline(self.symbol, '1d', days=120)
        except Exception:
            pass

        # 资金费率
        try:
            self.data['funding'] = get_funding_rate(self.symbol, limit=30)
        except Exception:
            pass

        # 持仓量
        try:
            self.data['oi'] = get_open_interest(self.symbol)
            self.data['oi_hist'] = get_open_interest_hist(self.symbol, period='1h', limit=24)
        except Exception:
            pass

    def analyze_technical(self) -> dict:
        """技术面分析"""
        result = {'score': 50, 'signals': []}
        kline = self.data.get('kline')

        if kline is not None and len(kline) > 60:
            kline = calc_all_indicators(kline)
            signals = analyze_signals(kline)

            for name, signal in signals.items():
                result['signals'].append(f"{name}: {signal}")
                if '🟢' in signal:
                    result['score'] += 5
                elif '🔴' in signal:
                    result['score'] -= 5

        self.analysis['technical'] = result
        return result

    def analyze_funding(self) -> dict:
        """资金费率分析"""
        result = {'score': 50, 'signals': []}
        funding = self.data.get('funding')

        if funding is not None and len(funding) > 0:
            latest_rate = funding['fundingRate'].iloc[-1]
            avg_rate = funding['fundingRate'].mean()

            if latest_rate > 0.001:
                result['score'] -= 10
                result['signals'].append(f'🔴 资金费率偏高 ({latest_rate*100:.4f}%)，多头拥挤')
            elif latest_rate < -0.001:
                result['score'] += 10
                result['signals'].append(f'🟢 资金费率为负 ({latest_rate*100:.4f}%)，空头拥挤')
            else:
                result['signals'].append(f'⚪ 资金费率正常 ({latest_rate*100:.4f}%)')

            # 费率趋势
            recent_avg = funding['fundingRate'].tail(8).mean()
            if recent_avg > avg_rate * 1.5:
                result['signals'].append('🔴 近期费率上升，市场过热')
                result['score'] -= 5
            elif recent_avg < avg_rate * 0.5:
                result['signals'].append('🟢 近期费率下降，市场降温')
                result['score'] += 5

        self.analysis['funding'] = result
        return result

    def analyze_oi(self) -> dict:
        """持仓量分析"""
        result = {'score': 50, 'signals': []}
        oi_hist = self.data.get('oi_hist')

        if oi_hist is not None and len(oi_hist) > 1:
            latest = oi_hist['sumOpenInterestValue'].iloc[-1]
            prev = oi_hist['sumOpenInterestValue'].iloc[0]
            change = (latest - prev) / prev * 100

            if change > 10:
                result['signals'].append(f'🟢 持仓量增长 {change:.1f}%，市场活跃度上升')
                result['score'] += 10
            elif change < -10:
                result['signals'].append(f'🔴 持仓量下降 {change:.1f}%，市场活跃度下降')
                result['score'] -= 5
            else:
                result['signals'].append(f'⚪ 持仓量变化 {change:.1f}%，基本稳定')

            result['signals'].append(f'当前持仓价值: ${latest:,.0f}')

        self.analysis['oi'] = result
        return result

    def analyze_momentum(self) -> dict:
        """动量分析"""
        result = {'score': 50, 'signals': []}
        ticker = self.data.get('ticker')

        if ticker:
            change_24h = float(ticker.get('priceChangePercent', 0))
            volume = float(ticker.get('quoteVolume', 0))

            if change_24h > 5:
                result['score'] += 15
                result['signals'].append(f'🟢 24h大涨 {change_24h:+.2f}%')
            elif change_24h > 2:
                result['score'] += 8
                result['signals'].append(f'🟢 24h上涨 {change_24h:+.2f}%')
            elif change_24h < -5:
                result['score'] -= 15
                result['signals'].append(f'🔴 24h大跌 {change_24h:+.2f}%')
            elif change_24h < -2:
                result['score'] -= 8
                result['signals'].append(f'🔴 24h下跌 {change_24h:+.2f}%')
            else:
                result['signals'].append(f'⚪ 24h变化 {change_24h:+.2f}%')

            result['signals'].append(f'24h成交额: ${volume/1e9:.2f}B')

        self.analysis['momentum'] = result
        return result

    def get_total_score(self) -> int:
        """综合评分"""
        weights = {'technical': 0.40, 'momentum': 0.25, 'funding': 0.20, 'oi': 0.15}
        scores = []
        for key, weight in weights.items():
            if key in self.analysis:
                scores.append(self.analysis[key]['score'] * weight)
        return int(sum(scores)) if scores else 50

    def get_recommendation(self, score: int) -> str:
        if score >= 75:
            return "🟢 **强烈看多** - 多项指标看涨，可考虑做多"
        elif score >= 60:
            return "🟢 **看多** - 整体偏多，可择机入场"
        elif score >= 45:
            return "⚪ **中性观望** - 信号不明确，建议观望"
        elif score >= 35:
            return "🔴 **看空** - 多项指标偏弱，注意风险"
        else:
            return "🔴 **强烈看空** - 风险较大，建议回避或做空"

    def generate_report(self) -> str:
        """生成分析报告"""
        print(f"正在分析 {self.symbol}...")
        self.fetch_data()
        self.analyze_technical()
        self.analyze_momentum()
        self.analyze_funding()
        self.analyze_oi()

        total_score = self.get_total_score()
        recommendation = self.get_recommendation(total_score)

        ticker = self.data.get('ticker', {})
        price = float(ticker.get('lastPrice', 0)) if ticker else 0

        lines = [
            f"# {self.base} 综合分析报告\n",
            f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**当前价格**: ${price:,.2f}\n",
            "---\n",
            f"## 综合评分: {total_score}/100\n",
            f"{recommendation}\n",
            "---\n",
        ]

        # 各维度
        dimension_names = {
            'technical': '📉 技术面分析 (权重 40%)',
            'momentum': '📊 动量分析 (权重 25%)',
            'funding': '💰 资金费率分析 (权重 20%)',
            'oi': '📈 持仓量分析 (权重 15%)',
        }

        for key, name in dimension_names.items():
            if key in self.analysis:
                data = self.analysis[key]
                lines.append(f"### {name} (得分: {data['score']})\n")
                for signal in data['signals']:
                    lines.append(f"- {signal}")
                lines.append("")

        # 行情信息
        if ticker:
            lines.append("---\n")
            lines.append("## 基本信息\n")
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            lines.append(f"| 最新价 | ${price:,.2f} |")
            lines.append(f"| 24h涨跌 | {float(ticker.get('priceChangePercent', 0)):+.2f}% |")
            lines.append(f"| 24h最高 | ${float(ticker.get('highPrice', 0)):,.2f} |")
            lines.append(f"| 24h最低 | ${float(ticker.get('lowPrice', 0)):,.2f} |")
            lines.append(f"| 24h成交量 | {float(ticker.get('volume', 0)):,.2f} {self.base} |")
            lines.append(f"| 24h成交额 | ${float(ticker.get('quoteVolume', 0)):,.0f} |")

        lines.append("\n---")
        lines.append("> 以上分析仅供参考，不构成投资建议。加密货币波动极大，请谨慎投资。")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='加密货币综合分析')
    parser.add_argument('symbol', help='交易对 (如 BTCUSDT)')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    analyzer = CryptoAnalyzer(args.symbol)
    report = analyzer.generate_report()

    print(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n已保存至: {args.output}")


if __name__ == '__main__':
    main()
