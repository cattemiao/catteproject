"""Apple Music 评论数据爬虫（JS 逆向骨架）。

需求中提到需要破解 JS 加密参数（params / encSecKey 基于 AES + RSA）。
这里提供加密逻辑的骨架实现，实际密钥/偏移量需根据 JS 逆向结果填充。
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import math
import random

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

from app.services.crawler.anti_crawl import make_session, random_delay

logger = logging.getLogger(__name__)

# —— 以下常量为 JS 逆向所得，占位值需替换为真实值 ——
PRESET_KEY = b"0CoJUm6Qyw8W8jud"      # AES 固定密钥
IV = b"0102030405060708"               # AES CBC 偏移量
PUBLIC_KEY_MODULUS = "00e0b509f625..."  # RSA 公钥模数（占位）
PUBLIC_KEY_EXPONENT = 0x10001
CHARSET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _aes_encrypt(text: str, key: bytes) -> str:
    """AES-CBC-PKCS7 加密后 Base64 编码。"""
    pad = 16 - len(text.encode("utf-8")) % 16
    text = text + chr(pad) * pad
    cipher = AES.new(key, AES.MODE_CBC, IV)
    encrypted = cipher.encrypt(text.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def _rsa_encrypt(random_key: str) -> str:
    """RSA 加密随机秘钥，返回十六进制字符串。"""
    # 构造公钥（模数需替换为真实值）
    modulus = int(PUBLIC_KEY_MODULUS, 16)
    pub_key = RSA.construct((modulus, PUBLIC_KEY_EXPONENT))
    cipher = PKCS1_v1_5.new(pub_key)
    encrypted = cipher.encrypt(random_key.encode("utf-8"))
    return binascii.hexlify(encrypted).decode("utf-8")


def _create_secret_key(size: int = 16) -> str:
    return "".join(random.choice(CHARSET) for _ in range(size))


def encrypt_params(text: str) -> dict[str, str]:
    """还原 JS 加密逻辑，生成 params 与 encSecKey。"""
    random_key = _create_secret_key()
    params = _aes_encrypt(_aes_encrypt(text, PRESET_KEY), random_key.encode("utf-8"))
    enc_sec_key = _rsa_encrypt(random_key[::-1])
    return {"params": params, "encSecKey": enc_sec_key}


def crawl_comments(song_id: str, max_pages: int = 50) -> list[dict]:
    """抓取指定歌曲评论。

    Args:
        song_id: 歌曲标识
        max_pages: 最多抓取页数

    Returns:
        评论列表 [{content, likes, user}, ...]
    """
    session = make_session()
    all_comments: list[dict] = []

    for page in range(1, max_pages + 1):
        # 构造加密请求参数
        raw_data = json.dumps(
            {"rid": song_id, "offset": (page - 1) * 20, "limit": 20}
        )
        encrypted = encrypt_params(raw_data)

        try:
            # 实际接口 URL 需根据抓包替换
            resp = session.post(
                "https://music.example.com/api/v1/comment",
                data=encrypted,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("评论第 %d 页请求失败: %s", page, exc)
            break

        comments = data.get("comments", [])
        if not comments:
            break

        for c in comments:
            all_comments.append(
                {
                    "content": c.get("content", ""),
                    "likes": c.get("likeCount", 0),
                    "user": c.get("user", {}).get("nickname", ""),
                }
            )

        random_delay()

    logger.info("歌曲 %s 共爬取 %d 条评论", song_id, len(all_comments))
    return all_comments
