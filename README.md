# crypto-kit

币安加密货币数据分析工具箱。配合 Hermes Agent 使用，支持微信对话交互。

## 功能概览

- **实时行情**：BTC/ETH 等所有币安 USDT 交易对的实时价格、涨跌幅、成交量、盘口深度
- **K 线数据**：现货和合约 K 线，支持 1m 到 1M 全部周期，优先读取本地 Parquet 数据
- **合约数据**：USDT 永续合约 K 线、资金费率历史、持仓量
- **技术指标**：MA(7/25/99)、MACD(12/26/9)、RSI(6/12/24)、KDJ、BOLL
- **综合分析**：四维度加权评分模型（技术面40% + 动量25% + 资金费率20% + 持仓量15%）
- **策略回测**：MA 均线交叉策略、RSI 超买超卖策略，输出收益率、胜率、最大回撤
- **模拟交易**：纸上交易系统，支持买入/卖出/持仓查看/交易历史，不涉及真实资金
- **历史数据下载**：批量下载 K 线数据到本地 Parquet，支持增量更新

## 安装

```bash
# Python 依赖
pip3 install requests pandas numpy pyarrow
```

## 快速开始

### 1. 实时行情

```bash
cd crypto-kit-skills/scripts

# 单币种行情
python3 get_realtime.py BTCUSDT

# 主流币概览（前10）
python3 get_realtime.py --all

# 盘口深度
python3 get_realtime.py BTCUSDT --depth
```

### 2. K 线数据

```bash
# 现货日 K 线（最近60天）
python3 get_kline.py BTCUSDT --days 60

# 4 小时 K 线
python3 get_kline.py ETHUSDT -i 4h --days 30

# 可以省略 USDT 后缀
python3 get_kline.py BTC --days 30

# 合约 K 线
python3 get_futures_kline.py BTCUSDT --days 30

# 资金费率历史
python3 get_futures_kline.py BTCUSDT --funding

# 持仓量
python3 get_futures_kline.py BTCUSDT --oi
```

### 3. 技术分析

```bash
# 技术指标（MA/MACD/RSI/KDJ/BOLL）
python3 calc_technical.py BTCUSDT

# 综合分析（四维度评分）
python3 analyze_crypto.py BTCUSDT
```

### 4. 策略回测

```bash
# MA 均线交叉回测
python3 backtest.py ma BTCUSDT --days 365

# 自定义均线参数
python3 backtest.py ma BTCUSDT --fast 7 --slow 25 --days 365

# RSI 超买超卖回测
python3 backtest.py rsi BTCUSDT --days 180
```

### 5. 模拟交易

```bash
# 重置账户（初始资金 10000 USDT）
python3 simulate_trade.py reset --capital 10000

# 按 USDT 金额买入
python3 simulate_trade.py buy BTCUSDT --usdt 5000

# 按数量买入
python3 simulate_trade.py buy ETHUSDT 1.5

# 全部卖出
python3 simulate_trade.py sell BTCUSDT --all

# 查看账户状态
python3 simulate_trade.py status

# 查看交易历史
python3 simulate_trade.py history
```

### 6. 历史数据下载

```bash
cd crypto-kit-skills/local

# 下载 BTC/ETH 日线（默认2年）
python3 download_history.py

# 下载 49 只主流币全量日线（上市至今，约8分钟）
python3 download_history.py --all

# 下载 49 只主流币最近2年日线
python3 download_history.py --all --days 730

# 指定币种和周期
python3 download_history.py --symbols BTCUSDT ETHUSDT SOLUSDT --interval 1h --days 90

# 增量更新（已下载的币种）
python3 download_history.py --update

# 下载合约数据
python3 download_history.py --futures

# 查看数据摘要
python3 download_history.py --summary
```

## API 域名与网络

所有数据通过币安公开 API 获取，**无需 API Key**。

脚本内置域名自动回退机制（`api_client.py`），优先试主域名，3 秒超时快速跳过被墙的：

| 域名 | 用途 | 国内阿里云 | 美国 IP |
|------|------|-----------|---------|
| `api.binance.com` | 现货 API | 超时（被墙） | 451 |
| `data-api.binance.vision` | 现货数据 API | **可用** | **可用** |
| `fapi.binance.com` | 合约 API | 超时（被墙） | 451 |
| `testnet.binancefuture.com` | 合约测试网 | **可用** | **可用** |

实际效果：国内服务器自动走 `data-api.binance.vision`（现货）+ `testnet.binancefuture.com`（合约），美国 IP 同理。无需手动配置。

testnet 的行情价格、资金费率与主网同步，持仓量历史 endpoint 不存在（非关键功能）。

## 综合分析评分模型

`analyze_crypto.py` 使用四维度加权评分（满分 100）：

| 维度 | 权重 | 评分依据 |
|------|------|---------|
| 技术面 | 40% | 均线趋势、MACD/RSI/KDJ/BOLL 信号 |
| 动量 | 25% | 24h 涨跌幅、成交量变化 |
| 资金费率 | 20% | 合约市场多空情绪 |
| 持仓量 | 15% | 市场参与度变化 |

评分参考：75+ 强烈看多 / 60-75 看多 / 45-60 中性观望 / 35-45 看空 / <35 强烈看空

## 缓存机制

脚本使用 SQLite 缓存（`.cache/binance_cache.db`），避免重复请求被限速：

| 数据类型 | 缓存过期时间 |
|---------|------------|
| 实时行情 | 30 秒 |
| 盘口深度 | 10 秒 |
| 日 K 线 | 1 小时 |
| 小时 K 线 | 30 分钟 |
| 资金费率/持仓量 | 5 分钟 |

如遇数据异常，先删缓存再重试：`rm crypto-kit-skills/.cache/binance_cache.db`

## 测试

### 全量测试（30 项）

```bash
bash test_all.sh
```

覆盖全部功能：

| 类别 | 测试内容 | 对应脚本 |
|------|---------|---------|
| 依赖检查 | Python/pandas/requests/numpy | — |
| 实时行情 | BTC/ETH 行情、主流币概览、盘口深度 | `get_realtime.py` |
| 现货 K 线 | 日 K/4h K/省略后缀 | `get_kline.py` |
| 合约数据 | 合约 K 线、资金费率、持仓量 | `get_futures_kline.py` |
| 技术指标 | BTC/ETH 技术分析 | `calc_technical.py` |
| 策略回测 | MA 回测、RSI 回测 | `backtest.py` |
| 综合分析 | BTC/ETH 综合评分 | `analyze_crypto.py` |
| 模拟交易 | 重置/买入/卖出/状态/历史 | `simulate_trade.py` |
| 数据下载 | 数据摘要 | `download_history.py` |
| 缓存管理 | 缓存状态 | `cache_manager.py` |

### 其他币种测试

```bash
bash test_other_coins.sh
```

测试 SOL/DOGE/XRP/ADA/AVAX 的行情、技术分析、回测、模拟交易。

## 项目结构

```
crypto-kit/
├── README.md                          # 本文件
├── test_all.sh                        # 全量测试（30项）
├── test_other_coins.sh                # 其他币种测试
└── crypto-kit-skills/             # Hermes Skill 目录（hermes skills install 安装这个）
    ├── SKILL.md                       # Skill 定义（Hermes 读取）
    ├── config.yaml                    # 配置文件
    ├── scripts/                       # 数据查询和分析脚本
    │   ├── api_client.py              # API 客户端（域名自动回退）
    │   ├── get_realtime.py            # 实时行情
    │   ├── get_kline.py               # 现货 K 线
    │   ├── get_futures_kline.py       # 合约 K 线 / 资金费率 / 持仓量
    │   ├── calc_technical.py          # 技术指标 MA/MACD/RSI/KDJ/BOLL
    │   ├── analyze_crypto.py          # 综合分析（四维度评分）
    │   ├── backtest.py                # 策略回测
    │   ├── simulate_trade.py          # 模拟交易
    │   └── cache_manager.py           # SQLite 缓存管理
    ├── local/                         # 本地数据工具
    │   └── download_history.py        # 历史数据批量下载
    ├── data/                          # 数据目录（Parquet，不提交）
    └── .cache/                        # 缓存目录（SQLite，不提交）
```

## Hermes 部署

### 安装 Skill

```bash
# 安装 Python 依赖
pip3 install requests pandas numpy pyarrow

# 从 GitHub 安装 Skill 到 Hermes
hermes skills install new0hand/crypto-kit/crypto-kit-skills --force
```

### 下载历史数据（可选）

```bash
# 克隆仓库
git clone https://github.com/<用户名>/crypto-kit.git
cd crypto-kit/crypto-kit-skills/local

# 下载 BTC/ETH 两年日线
python3 download_history.py

# 验证
cd ../..
bash test_all.sh
```

### 更新 Skill

```bash
hermes skills install new0hand/crypto-kit/crypto-kit-skills --force
```

### 微信网关

```bash
hermes gateway setup
hermes pairing approve weixin XXXX
```

## Hermes 对话测试

安装完成后，在 Hermes 对话中（微信或终端）发送以下提示词验证功能：

### 行情查询

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 查一下比特币现在多少钱 | 实时行情 `get_realtime.py` | 1-2秒 |
| 看看主流币行情 | 主流币概览 `get_realtime.py --all` | 2-3秒 |
| BTC 的盘口深度 | 盘口 `get_realtime.py --depth` | 1-2秒 |

### K 线和技术指标

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 帮我看看 BTC 最近 60 天的 K 线 | 现货 K 线 `get_kline.py` | 2-3秒 |
| ETH 4 小时 K 线最近一周的 | 小时 K 线 `get_kline.py -i 4h` | 2-3秒 |
| 分析一下 BTC 的技术指标 | 技术指标 `calc_technical.py` | 2-3秒 |

### 合约数据

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| BTC 合约最近 30 天的 K 线 | 合约 K 线 `get_futures_kline.py` | 2-3秒 |
| ETH 合约 4 小时 K 线 | 合约小时 K 线 `get_futures_kline.py -i 4h` | 2-3秒 |
| BTC 的资金费率怎么样 | 资金费率历史 `get_futures_kline.py --funding` | 2-3秒 |
| 看看 BTC 的持仓量 | 持仓量 `get_futures_kline.py --oi` | 2-3秒 |
| ETH 合约资金费率最近一个月 | 资金费率 `get_futures_kline.py --funding` | 2-3秒 |

### 综合分析

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 帮我分析一下 BTC 值不值得买 | 综合分析 `analyze_crypto.py` | 5-8秒 |
| 给我出一份 ETH 的分析报告 | 综合分析 `analyze_crypto.py` | 5-8秒 |

### 策略回测

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 帮我回测 BTC 的均线策略，最近一年 | MA 回测 `backtest.py ma` | 5-10秒 |
| 用 RSI 策略回测一下 ETH | RSI 回测 `backtest.py rsi` | 5-10秒 |

### 模拟交易

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 帮我用 5000U 买入 BTC | 模拟买入 `simulate_trade.py buy` | 1-2秒 |
| 把 BTC 全卖了 | 模拟卖出 `simulate_trade.py sell` | 1-2秒 |
| 看看我的模拟账户 | 账户状态 `simulate_trade.py status` | 1-2秒 |
| 查看交易记录 | 交易历史 `simulate_trade.py history` | 秒级 |

## 定时更新（crontab）

加密货币 7×24 小时交易，建议每天更新一次：

```bash
# 打开 crontab
crontab -e

# 每天凌晨 2 点增量更新
0 2 * * * cd ~/.hermes/skills/crypto-kit-skills/local && /usr/bin/python3 download_history.py --update >> /tmp/crypto-update.log 2>&1
```

### macOS 注意事项

macOS 需要给 cron 授权"完全磁盘访问权限"：系统设置 → 隐私与安全性 → 完全磁盘访问权限 → + → `Cmd+Shift+G` → `/usr/sbin/cron`

## 支持的交易对

所有币安 USDT 交易对均可使用。输入时可以省略 USDT 后缀，如 `BTC` 等价于 `BTCUSDT`。

### 主流币列表（`--all` 下载，49 只）

| 分类 | 币种 |
|------|------|
| 市值 Top 10 | BTC, ETH, BNB, SOL, XRP, DOGE, ADA, TRX, AVAX, LINK |
| 市值 11-25 | DOT, MATIC, SHIB, LTC, NEAR, UNI, APT, ICP, ETC, FIL, ATOM, XLM, ARB, OP, SUI |
| 市值 26-40 | INJ, FTM, TIA, SEI, RUNE, GRT, AAVE, MKR, ALGO, SAND, AXS, MANA, SNX, LDO, APE |
| AI / 新叙事 | FET, RENDER, WLD |
| Meme | PEPE, FLOKI |
| 其他主流 | EOS, VET, THETA, XTZ |

## 免责声明

本工具仅供学习和研究使用。加密货币市场波动极大，所有分析结果和交易信号仅供参考，不构成任何投资建议。使用本工具进行的任何交易决策，风险由使用者自行承担。
