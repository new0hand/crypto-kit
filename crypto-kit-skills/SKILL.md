---
name: crypto-kit-skills
description: 使用币安公开 API 获取和分析加密货币数据。支持：BTC/ETH 实时行情、现货和合约 K 线、技术指标分析、策略回测、模拟交易、资金费率、持仓量分析。当用户需要查询加密货币价格、分析 BTC/ETH 走势、回测交易策略、进行模拟交易时使用此 skill。
---

# 币安加密货币分析 Skill

> **重要规则：所有数据查询必须使用 scripts/ 或 local/ 目录下的 Python 脚本。禁止自己用 curl 调用任何 API。禁止自己编写或创建文件。脚本内部已实现完整功能，不需要额外方案。**

使用币安公开 API 获取加密货币数据并进行分析。无需 API Key 即可查询行情和 K 线。

## 快速开始

### 环境准备

```bash
pip install requests pandas numpy pyarrow
```

### 常用命令

```bash
cd scripts

# 综合分析（推荐）
python analyze_crypto.py BTCUSDT

# 实时行情
python get_realtime.py BTCUSDT

# 主流币种概览
python get_realtime.py --all

# K 线数据
python get_kline.py BTCUSDT --days 60

# 技术指标
python calc_technical.py BTCUSDT

# 策略回测
python backtest.py ma BTCUSDT --days 365

# 模拟交易
python simulate_trade.py buy BTCUSDT --usdt 1000
python simulate_trade.py status
```

## 脚本列表

### 数据获取脚本

| 脚本 | 功能 | 示例 |
|------|------|------|
| `get_realtime.py` | 实时行情（价格/涨跌/成交量） | `python get_realtime.py BTCUSDT` |
| `get_realtime.py --all` | 主流币种概览（10个） | `python get_realtime.py --all` |
| `get_realtime.py --depth` | 盘口深度 | `python get_realtime.py BTCUSDT --depth` |
| `get_kline.py` | 现货 K 线 | `python get_kline.py BTCUSDT --days 60` |
| `get_kline.py -i 1h` | 指定周期 K 线 | `python get_kline.py ETHUSDT -i 4h --days 30` |
| `get_futures_kline.py` | 合约 K 线 | `python get_futures_kline.py BTCUSDT --days 30` |
| `get_futures_kline.py --funding` | 资金费率 | `python get_futures_kline.py BTCUSDT --funding` |
| `get_futures_kline.py --oi` | 持仓量 | `python get_futures_kline.py BTCUSDT --oi` |

### 分析脚本

| 脚本 | 功能 | 示例 |
|------|------|------|
| `analyze_crypto.py` | 综合分析（技术面+资金费率+持仓量） | `python analyze_crypto.py BTCUSDT` |
| `calc_technical.py` | 技术指标（MA/MACD/RSI/KDJ/BOLL） | `python calc_technical.py BTCUSDT` |
| `backtest.py ma` | MA均线交叉回测 | `python backtest.py ma BTCUSDT --days 365` |
| `backtest.py rsi` | RSI超买超卖回测 | `python backtest.py rsi BTCUSDT` |
| `backtest.py ma --all` | 批量回测49只主流币（需本地数据） | `python backtest.py ma --all --days 730` |
| `backtest.py ma --all --top 10` | 只显示收益前10名 | `python backtest.py ma --all --top 10` |

### 交易脚本

| 脚本 | 功能 | 示例 |
|------|------|------|
| `simulate_trade.py buy` | 模拟买入 | `python simulate_trade.py buy BTCUSDT --usdt 500` |
| `simulate_trade.py sell` | 模拟卖出 | `python simulate_trade.py sell BTCUSDT --all` |
| `simulate_trade.py status` | 查看模拟账户 | `python simulate_trade.py status` |
| `simulate_trade.py history` | 交易历史 | `python simulate_trade.py history` |
| `simulate_trade.py reset` | 重置模拟账户 | `python simulate_trade.py reset --capital 50000` |

### 本地数据工具

> **路径注意**：scripts/ 下的脚本用 `cd scripts` 后执行；local/ 下的脚本用 `cd local` 后执行。两个目录是平级的，不要混用。

```bash
cd local

# 下载 49 只主流币全量日线（上市至今，约8分钟）
python download_history.py --all

# 下载 49 只主流币最近2年日线
python download_history.py --all --days 730

# 下载指定币种
python download_history.py --symbols BTCUSDT ETHUSDT SOLUSDT

# 增量更新（已下载的币种）
python download_history.py --update

# 下载合约数据
python download_history.py --futures

# 查看数据摘要
python download_history.py --summary
```

## 支持的交易对

默认支持所有币安 USDT 交易对，常用的包括：
- **BTCUSDT** - 比特币
- **ETHUSDT** - 以太坊
- **BNBUSDT** - 币安币
- **SOLUSDT** - Solana
- **XRPUSDT** - 瑞波币
- **DOGEUSDT** - 狗狗币

输入时可以省略 USDT 后缀，脚本会自动补全。如 `BTC` 等价于 `BTCUSDT`。

## K 线周期

支持的 K 线周期：`1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M`

## 核心功能

### 1. 综合分析

```bash
python analyze_crypto.py BTCUSDT
```

四维度加权评分（满分100）：
- 📉 技术面分析（40%）：均线/MACD/RSI/KDJ/BOLL
- 📊 动量分析（25%）：24h 涨跌幅、成交量
- 💰 资金费率分析（20%）：合约市场多空情绪
- 📈 持仓量分析（15%）：市场参与度

评分参考：75+ 强烈看多 / 60-75 看多 / 45-60 中性观望 / <35 强烈看空

### 2. 技术指标

```bash
python calc_technical.py BTCUSDT
```

- **MA**: 7/25/99日均线（加密货币常用）
- **MACD**: DIF, DEA, MACD柱（12/26/9）
- **RSI**: 6/12/24日
- **KDJ**: K, D, J
- **BOLL**: 上轨/中轨/下轨（20日 ± 2标准差）

### 3. 策略回测

```bash
# MA 均线交叉策略
python backtest.py ma BTCUSDT --fast 7 --slow 25 --days 365

# RSI 超买超卖策略
python backtest.py rsi BTCUSDT --oversold 30 --overbought 70

# 批量回测所有主流币（49只，按收益排名）
python backtest.py ma --all --days 730

# 只看收益最高的前10
python backtest.py ma --all --days 730 --top 10

# RSI 策略批量回测
python backtest.py rsi --all --days 365
```

> **批量回测说明**：`--all` 会回测 49 只主流币，优先使用本地 Parquet 数据（秒级），无本地数据时从 API 获取（较慢）。建议先运行 `cd local && python download_history.py --all` 下载本地数据。

### 4. 模拟交易

纸上交易，不涉及真实资金：

```bash
# 初始化 / 重置账户
python simulate_trade.py reset --capital 10000

# 买入
python simulate_trade.py buy BTC --usdt 5000
python simulate_trade.py buy ETH 1.5

# 卖出
python simulate_trade.py sell BTC --all

# 查看状态
python simulate_trade.py status
```

### 5. 合约数据

```bash
# 合约 K 线
python get_futures_kline.py BTCUSDT -i 4h --days 30

# 资金费率
python get_futures_kline.py BTCUSDT --funding

# 持仓量
python get_futures_kline.py BTCUSDT --oi
```

## 数据缓存

自动缓存避免重复请求（SQLite）：
- 实时行情：30秒
- 日K线：1小时
- 小时K线/合约K线：30分钟
- 资金费率/持仓量：5分钟

如遇数据异常，删缓存重试：`rm .cache/binance_cache.db`

## API 说明

- 所有行情和 K 线查询使用**币安公开 API**，无需 API Key
- 公开 API 限速：1200 次/分钟，正常使用不会触发
- 模拟交易在本地运行，不连接交易所
- 合约数据使用 `fapi.binance.com`（USDT 永续合约）
- 阿里云服务器可直连币安 API，无需代理

## 输出格式

所有脚本默认输出 **Markdown** 格式：

```bash
python analyze_crypto.py BTCUSDT -o 分析报告.md
```

## 文件结构

```
crypto-kit-skills/
├── SKILL.md                     # 本文档
├── config.yaml                  # 配置文件
├── scripts/                     # 数据查询和分析脚本
│   ├── get_realtime.py          # 实时行情
│   ├── get_kline.py             # 现货K线
│   ├── get_futures_kline.py     # 合约K线/资金费率/持仓量
│   ├── calc_technical.py        # 技术指标
│   ├── analyze_crypto.py        # 综合分析
│   ├── backtest.py              # 策略回测
│   ├── simulate_trade.py        # 模拟交易
│   └── cache_manager.py         # 缓存管理
├── local/                       # 本地数据工具
│   └── download_history.py      # 历史数据下载
├── data/                        # 数据目录（Parquet 文件）
└── .cache/                      # 缓存目录（SQLite）
```

## 免责声明

本工具仅供学习和研究使用。加密货币市场波动极大，所有分析结果和交易信号仅供参考，不构成任何投资建议。使用本工具进行的任何交易决策，风险由使用者自行承担。
