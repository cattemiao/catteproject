"""网易云音乐客户端：二维码登录、最近播放、歌曲入库。"""
from __future__ import annotations

import logging
import time

from app.services.netease.weapi import qr_content, weapi_post

logger = logging.getLogger(__name__)

# 扫码状态码
QR_EXPIRED = 800
QR_WAITING = 801
QR_SCANNED = 802
QR_SUCCESS = 803

# 二维码会话缓存：key -> {"cookies": {...}, "created_at": ts}
# 网易云扫码轮询必须与创建二维码时保持同一会话（NMTID），否则状态永远无法关联
_QR_SESSIONS: dict[str, dict] = {}
_QR_SESSION_TTL = 600  # 10 分钟


def _get_qr_session(key: str) -> dict | None:
    session = _QR_SESSIONS.get(key)
    if not session:
        return None
    if time.time() - session["created_at"] > _QR_SESSION_TTL:
        _QR_SESSIONS.pop(key, None)
        return None
    return session


async def create_qr_key() -> dict:
    """生成登录二维码 key。返回 {key, content, error?}。"""
    payload, resp_cookies = await weapi_post("/login/qrcode/unikey", {"type": 1})
    key = payload.get("unikey", "") or payload.get("data", {}).get("unikey", "")
    if not key:
        return {"error": "获取二维码失败，请重试"}
    # 保存会话 cookie，轮询扫码时复用
    _QR_SESSIONS[key] = {"cookies": resp_cookies, "created_at": time.time()}
    return {"key": key, "content": qr_content(key)}


async def check_qr_status(key: str, prev_cookies: dict | None = None) -> dict:
    """轮询二维码扫码状态。

    code=803 时返回 {code, message, cookies, profile}
    """
    # 使用创建二维码时的会话 cookie
    session = _get_qr_session(key)
    session_cookies = session["cookies"] if session else None
    if prev_cookies:
        session_cookies = {**(session_cookies or {}), **prev_cookies}

    payload, resp_cookies = await weapi_post(
        "/login/qrcode/client/login",
        {"csrf_token": "", "key": key, "type": 1},
        cookies=session_cookies,
    )
    code = payload.get("code", QR_WAITING)
    result: dict = {"code": code, "message": payload.get("message", "")}

    if code == QR_EXPIRED:
        result["message"] = "二维码已过期，请刷新"
    elif code == QR_WAITING:
        result["message"] = "等待扫码..."
    elif code == QR_SCANNED:
        result["message"] = "已扫码，请在手机上确认"
    elif code == QR_SUCCESS:
        # 登录成功：cookie 在响应体 data.cookie（完整字符串），Set-Cookie 头兜底
        data = payload.get("data", {}) or {}
        merged = {**(session_cookies or {}), **resp_cookies}
        cookie_str = data.get("cookie") or ""
        if cookie_str:
            merged.update(parse_cookie_str(cookie_str))
        result["cookies"] = merged
        # 部分场景 803 响应带 profile，兜底用账号接口获取
        profile = data.get("profile", {})
        if not profile:
            profile = await _get_user_profile(merged)
        result["profile"] = profile
        result["message"] = "登录成功"
        _QR_SESSIONS.pop(key, None)

    return result


async def _get_user_profile(cookies: dict[str, str]) -> dict:
    """通过账号接口获取用户信息（二维码登录 803 响应不一定带完整 profile）。"""
    try:
        payload, _ = await weapi_post("/nuser/account/get", {}, cookies=cookies)
        return payload.get("profile", {}) or {}
    except Exception as exc:
        logger.warning("获取网易云用户信息失败: %s", exc)
        return {}


async def get_recent_played(
    cookies: dict[str, str],
    uid: int,
    limit: int = 10,
) -> list[dict]:
    """获取最近播放歌曲列表。"""
    payload, _ = await weapi_post(
        "/v1/play/record",
        {"uid": uid, "type": 1, "limit": min(limit, 20), "offset": 0},
        cookies=cookies,
    )
    records = payload.get("allData", []) or payload.get("weekData", [])
    songs = []
    for item in records[:limit]:
        s = item.get("song", {}) if isinstance(item, dict) else {}
        if not s:
            continue
        artists = s.get("ar", s.get("artists", []))
        artist_names = "、".join(
            [a.get("name", "") for a in artists if isinstance(a, dict)]
        )
        album = s.get("al", s.get("album", {})) or {}
        songs.append({
            "netease_id": str(s.get("id", "")),
            "title": s.get("name", ""),
            "artist": artist_names,
            "album": album.get("name", "") if isinstance(album, dict) else "",
            "duration_ms": s.get("dt", s.get("duration", 0)),
            "cover_url": (album.get("picUrl", "") if isinstance(album, dict) else "")
            or s.get("album", {}).get("picUrl", ""),
            "raw": s,
        })
    return songs


async def search_songs(
    keyword: str,
    limit: int = 10,
    timeout: float = 15.0,
) -> list[dict]:
    """搜索网易云歌曲（无需登录）。"""
    import httpx

    from app.services.crawler.anti_crawl import random_user_agent

    headers = {
        "User-Agent": random_user_agent(),
        "Referer": "https://music.163.com/",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    url = "https://music.163.com/api/search/get"
    params = {
        "s": keyword,
        "type": 1,
        "offset": 0,
        "limit": min(limit, 30),
        "total": "true",
    }
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as cli:
        try:
            resp = await cli.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("网易云搜索失败: %s (%s)", keyword, exc)
            return []

    songs = []
    for s in (data.get("result", {}) or {}).get("songs", [])[:limit]:
        artists = s.get("artists", [])
        artist_names = "、".join([a.get("name", "") for a in artists])
        album = s.get("album", {}) or {}
        songs.append({
            "netease_id": str(s.get("id", "")),
            "title": s.get("name", ""),
            "artist": artist_names,
            "album": album.get("name", ""),
            "duration_ms": s.get("duration", 0),
            "cover_url": album.get("picUrl", ""),
            "raw": s,
        })
    return songs


def parse_cookie_str(cookie_str: str) -> dict[str, str]:
    """把 cookie 字符串转成 dict。"""
    result: dict[str, str] = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            result[k.strip()] = v.strip()
    return result
