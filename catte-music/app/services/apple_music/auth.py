"""Apple Music 开发者 Token 生成与管理。

用 JWT 签发 Developer Token（需 Apple Developer 后台创建的 MusicKit Key）。
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx
from jose import jwt

from app.config import settings

API_BASE = "https://api.music.apple.com"
TOKEN_TTL = 180 * 24 * 3600  # 最多 180 天


def _read_private_key() -> str:
    key_path = Path(settings.apple_music_private_key_path)
    if not key_path.exists():
        raise FileNotFoundError(f"Apple Music 私钥不存在: {key_path}")
    return key_path.read_text(encoding="utf-8")


def generate_developer_token() -> str:
    """签发 Apple Music Developer Token (JWT)。

    Header: {alg: ES256, kid: KEY_ID}
    Payload: {iss: TEAM_ID, iat, exp}
    """
    if not settings.apple_music_key_id or not settings.apple_music_team_id:
        raise ValueError("请在 .env 中配置 APPLE_MUSIC_KEY_ID 和 APPLE_MUSIC_TEAM_ID")

    private_key = _read_private_key()
    now = int(time.time())
    payload = {
        "iss": settings.apple_music_team_id,
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    headers = {"kid": settings.apple_music_key_id, "alg": "ES256"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def get_developer_token() -> str:
    """获取 Developer Token：优先用环境变量中的，否则现签。"""
    if settings.apple_music_developer_token:
        return settings.apple_music_developer_token
    return generate_developer_token()
