"""网易云音乐 API 封装：weapi 加密、二维码登录、最近播放、搜索。

参考网页版网易云音乐（music.163.com）的 weapi 加密方式：
- params 先 AES-CBC（key=随机16位secret, iv 固定）再 RSA（裸 RSA：反转+大数幂模，结果 hex）。
"""
from __future__ import annotations

import base64
import json
import logging
import random
import string

import httpx
from Crypto.Cipher import AES

from app.services.crawler.anti_crawl import random_user_agent

logger = logging.getLogger(__name__)

NETEASE_BASE = "https://music.163.com/weapi"
NONCE = "0CoJUm6Qyw8W8jud"
IV = b"0102030405060708"
PUBLIC_KEY = "010001"
MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b7251"
    "52b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312e"
    "cbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d"
    "813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7"
)


def _pad(text: str) -> str:
    pad = 16 - len(text) % 16
    return text + chr(pad) * pad


def _aes_encrypt(text: str, key: str) -> str:
    cipher = AES.new(key.encode(), AES.MODE_CBC, IV)
    encrypted = cipher.encrypt(_pad(text).encode())
    return base64.b64encode(encrypted).decode()


def _rsa_encrypt(text: str) -> str:
    """裸 RSA：先反转字节，再大数幂模运算，输出 256 位 hex。"""
    reversed_text = text[::-1]
    num = int.from_bytes(reversed_text.encode(), "big")
    result = pow(num, int(PUBLIC_KEY, 16), int(MODULUS, 16))
    return format(result, "x").zfill(256)


def encrypt_weapi(data: dict) -> dict[str, str]:
    """将请求数据加密为 weapi 需要的 {params, encSecKey}。"""
    secret = "".join(random.sample(string.ascii_letters + string.digits, 16))
    params = _aes_encrypt(json.dumps(data, ensure_ascii=False), NONCE)
    params = _aes_encrypt(params, secret)
    return {
        "params": params,
        "encSecKey": _rsa_encrypt(secret),
    }


async def weapi_post(
    path: str,
    data: dict,
    cookies: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[dict, dict[str, str]]:
    """POST 到网易云 weapi 接口，返回 (json, 响应 cookie)。"""
    headers = {
        "User-Agent": random_user_agent(),
        "Referer": "https://music.163.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://music.163.com",
        "X-Real-IP": "223.72.106.88",
        "Cookie": "os=pc; appver=8.9.70;",
    }
    # 合并传入 cookie
    if cookies:
        extra = "; ".join(f"{k}={v}" for k, v in cookies.items())
        headers["Cookie"] = f"{headers['Cookie']} {extra}"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
        try:
            resp = await cli.post(
                f"{NETEASE_BASE}{path}",
                data=encrypt_weapi(data),
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()
            # 手动解析 Set-Cookie 头，避免 httpx cookie jar 同名冲突（如 MUSIC_A_T）
            resp_cookies: dict[str, str] = {}
            for set_cookie in resp.headers.get_list("set-cookie"):
                first = set_cookie.split(";", 1)[0]
                if "=" in first:
                    k, v = first.split("=", 1)
                    resp_cookies[k.strip()] = v.strip()
            return payload, resp_cookies
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("网易云 weapi 请求失败: %s (%s)", path, exc)
            return {}, {}


def qr_content(unikey: str) -> str:
    """构造二维码扫码地址（网易云 App 识别标准格式）。"""
    return f"http://music.163.com/login?codekey={unikey}"
