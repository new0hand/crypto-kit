# -*- coding: utf-8 -*-
"""
币安 API 客户端（带域名自动回退）

域名可用性（2026-05-10 实测）：
  - api.binance.com     → 中国大陆被墙，美国 451
  - data-api.binance.vision → 中国大陆可用，美国可用（仅现货）
  - fapi.binance.com    → 中国大陆被墙，美国 451
  - testnet.binancefuture.com → 中国大陆可用，美国可用（合约测试网，数据基本同步）

策略：优先试主域名（3秒超时，快速失败），不通则自动回退到备用域名。
阿里云国内服务器会走 data-api.binance.vision + testnet.binancefuture.com。

所有脚本应通过此模块发起请求，不要直接调 requests.get。
"""
import requests
import time
from typing import Optional

# 现货 API 域名（按优先级）
# data-api.binance.vision 放第二，国内外都通
SPOT_DOMAINS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]

# 合约 API 域名（按优先级）
# testnet 数据和主网基本同步，价格/资金费率/持仓量都有
FUTURES_DOMAINS = [
    "https://fapi.binance.com",
    "https://testnet.binancefuture.com",
]

# 缓存可用域名（避免每次请求都重试）
_spot_domain: Optional[str] = None
_futures_domain: Optional[str] = None


def _find_working_domain(domains: list, test_path: str, timeout: int = 3) -> Optional[str]:
    """测试并找到可用的域名（超时短，快速跳过被墙的）"""
    for domain in domains:
        try:
            resp = requests.get(f"{domain}{test_path}", timeout=timeout)
            if resp.status_code == 200:
                return domain
            # 451 = 地区限制，跳过
        except (requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout):
            # 被墙的域名会超时，快速跳过
            continue
        except Exception:
            continue
    return None


def get_spot_base() -> str:
    """获取可用的现货 API 基础 URL"""
    global _spot_domain
    if _spot_domain:
        try:
            resp = requests.get(f"{_spot_domain}/api/v3/ping", timeout=3)
            if resp.status_code == 200:
                return _spot_domain
        except Exception:
            pass
        _spot_domain = None

    _spot_domain = _find_working_domain(SPOT_DOMAINS, "/api/v3/ping")
    if _spot_domain:
        return _spot_domain

    # 全部失败，返回最可能通的备用域名
    return "https://data-api.binance.vision"


def get_futures_base() -> str:
    """获取可用的合约 API 基础 URL"""
    global _futures_domain
    if _futures_domain:
        try:
            resp = requests.get(f"{_futures_domain}/fapi/v1/ping", timeout=3)
            if resp.status_code == 200:
                return _futures_domain
        except Exception:
            pass
        _futures_domain = None

    _futures_domain = _find_working_domain(FUTURES_DOMAINS, "/fapi/v1/ping")
    if _futures_domain:
        return _futures_domain

    return "https://testnet.binancefuture.com"


def spot_get(path: str, params: dict = None, timeout: int = 10) -> requests.Response:
    """发起现货 API 请求（自动回退域名）"""
    base = get_spot_base()
    url = f"{base}{path}"

    try:
        resp = requests.get(url, params=params, timeout=timeout)
    except (requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout):
        # 主域名被墙，直接回退
        resp = None

    # 如果失败或 451，尝试其他域名
    if resp is None or resp.status_code in (451, 403):
        global _spot_domain
        _spot_domain = None
        for domain in SPOT_DOMAINS:
            if domain == base:
                continue
            try:
                url2 = f"{domain}{path}"
                resp2 = requests.get(url2, params=params, timeout=timeout)
                if resp2.status_code == 200:
                    _spot_domain = domain
                    return resp2
            except Exception:
                continue

    return resp


def futures_get(path: str, params: dict = None, timeout: int = 10) -> requests.Response:
    """发起合约 API 请求（自动回退域名）"""
    base = get_futures_base()
    url = f"{base}{path}"

    try:
        resp = requests.get(url, params=params, timeout=timeout)
    except (requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout):
        resp = None

    if resp is None or resp.status_code in (451, 403):
        global _futures_domain
        _futures_domain = None
        for domain in FUTURES_DOMAINS:
            if domain == base:
                continue
            try:
                url2 = f"{domain}{path}"
                resp2 = requests.get(url2, params=params, timeout=timeout)
                if resp2.status_code == 200:
                    _futures_domain = domain
                    return resp2
            except Exception:
                continue

    return resp


if __name__ == '__main__':
    print("测试现货 API 域名...")
    base = get_spot_base()
    print(f"  可用域名: {base}")

    print("测试合约 API 域名...")
    fbase = get_futures_base()
    print(f"  可用域名: {fbase}")

    print("\n测试请求 BTC 价格...")
    resp = spot_get("/api/v3/ticker/price", params={"symbol": "BTCUSDT"})
    print(f"  状态: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  数据: {resp.json()}")
