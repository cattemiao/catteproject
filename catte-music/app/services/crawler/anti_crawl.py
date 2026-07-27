"""反爬策略模块：随机 UA、智能延时、代理轮换、Session 管理。"""
from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import requests

# 常见浏览器 User-Agent 池
USER_AGENTS = [
    # Chrome Win/Mac/Linux
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Safari Mac/iOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]


def random_user_agent() -> str:
    """从 UA 池随机返回一个浏览器 User-Agent。"""
    return random.choice(USER_AGENTS)


def random_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """请求间随机休眠，模拟人类浏览节奏。"""
    time.sleep(random.uniform(min_s, max_s))


class ProxyPool:
    """简易代理 IP 轮换池。"""

    def __init__(self, proxies: list[str] | None = None) -> None:
        self._proxies: list[str] = proxies or []
        self._index = 0

    def add(self, proxy: str) -> None:
        self._proxies.append(proxy)

    def get(self) -> str | None:
        if not self._proxies:
            return None
        proxy = self._proxies[self._index % len(self._proxies)]
        self._index += 1
        return proxy

    def to_dict(self) -> dict | None:
        proxy = self.get()
        if proxy is None:
            return None
        return {"http": proxy, "https": proxy}

    def __len__(self) -> int:
        return len(self._proxies)


def make_session(
    proxy_pool: ProxyPool | None = None,
    timeout: float = 15.0,
) -> requests.Session:
    """返回带随机 UA、超时、重试的 requests.Session。"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.headers.update({"User-Agent": random_user_agent()})

    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    if proxy_pool is not None:
        proxies = proxy_pool.to_dict()
        if proxies:
            session.proxies.update(proxies)

    session.timeout = timeout  # type: ignore[attr-defined]
    return session


# ── 便捷函数 ──

def safe_get(url: str, **kwargs) -> requests.Response | None:
    """带反爬策略的 GET 请求，异常时返回 None。"""
    import requests as req

    session = make_session()
    random_delay(0.5, 2.0)
    try:
        resp = session.get(url, **kwargs)
        resp.raise_for_status()
        return resp
    except req.RequestException:
        return None


def rotate_headers() -> dict[str, str]:
    """返回一组随机浏览器头，包含 Accept-Language / Referer 等。"""
    languages = ["zh-CN,zh;q=0.9,en;q=0.8", "en-US,en;q=0.9,zh-CN;q=0.8"]
    return {
        "User-Agent": random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(languages),
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
    }