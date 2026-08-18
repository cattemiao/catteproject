"""网易云音乐客户端：二维码登录、最近播放、歌曲入库。"""
from __future__ import annotations

import logging
import time

import httpx

from app.services.crawler.anti_crawl import random_user_agent
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
    # 实测网易云接口：type=0 返回 allData（全部播放记录），type=1 返回 weekData（最近一周）
    payload, _ = await weapi_post(
        "/v1/play/record",
        {"uid": uid, "type": 0, "limit": min(limit, 20), "offset": 0},
        cookies=cookies,
    )
    records = payload.get("allData", []) or payload.get("weekData", [])
    songs = []
    for item in records[:limit]:
        s = item.get("song", {}) if isinstance(item, dict) else {}
        if not s:
            continue
        songs.append(_parse_song(s))
    return songs


def _parse_song(s: dict) -> dict:
    """把网易云歌曲对象转为统一结构。"""
    artists = s.get("ar", s.get("artists", []))
    artist_names = "、".join(
        [a.get("name", "") for a in artists if isinstance(a, dict)]
    )
    album = s.get("al", s.get("album", {})) or {}
    return {
        "netease_id": str(s.get("id", "")),
        "title": s.get("name", ""),
        "artist": artist_names,
        "album": album.get("name", "") if isinstance(album, dict) else "",
        "duration_ms": s.get("dt", s.get("duration", 0)),
        "track_number": s.get("no"),
        "cover_url": (album.get("picUrl", "") if isinstance(album, dict) else "")
        or s.get("album", {}).get("picUrl", ""),
        "raw": s,
    }


async def get_album_tracks(
    album_id: str,
    cookies: dict[str, str] | None = None,
    limit: int = 200,
) -> list[dict]:
    """获取专辑曲目（weapi /v1/album/{id}）。"""
    payload, _ = await weapi_post(f"/v1/album/{album_id}", {}, cookies=cookies)
    songs = payload.get("songs") or []
    return [_parse_song(s) for s in songs[:limit]]


async def get_playlist_tracks(
    playlist_id: str,
    cookies: dict[str, str] | None = None,
    limit: int = 200,
) -> list[dict]:
    """获取歌单曲目（weapi /v6/playlist/detail，n=100000 拉全量）。"""
    payload, _ = await weapi_post(
        "/v6/playlist/detail",
        {"id": int(playlist_id), "n": 100000, "s": 8},
        cookies=cookies,
    )
    playlist = payload.get("playlist") or {}
    songs = playlist.get("tracks") or []
    return [_parse_song(s) for s in songs[:limit]]


def _api_headers(cookies: dict[str, str]) -> dict[str, str]:
    """构造网易云普通 api 接口请求头（非 weapi 加密）。"""
    return {
        "User-Agent": random_user_agent(),
        "Referer": "https://music.163.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://music.163.com",
        "Cookie": "os=pc; appver=8.9.70; "
        + "; ".join(f"{k}={v}" for k, v in cookies.items()),
    }


async def get_subscribed_playlists(
    cookies: dict[str, str],
    uid: int,
    limit: int = 100,
) -> list[dict]:
    """获取用户收藏的歌单（排除自己创建的与"我喜欢的音乐"特殊歌单）。"""
    headers = _api_headers(cookies)
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as cli:
            resp = await cli.post(
                "https://music.163.com/api/user/playlist",
                data={"uid": uid, "limit": 100, "offset": 0},
                headers=headers,
            )
            playlists = (resp.json().get("playlist") or []) or []
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("网易云收藏歌单获取失败: %s", exc)
        return []

    result = []
    for p in playlists:
        if p.get("specialType") == 5:
            continue  # 我喜欢的音乐（特殊歌单）
        if p.get("userId") == uid:
            continue  # 自己创建的歌单
        creator = p.get("creator") or {}
        result.append({
            "netease_id": str(p.get("id", "")),
            "title": p.get("name", ""),
            "artist": creator.get("nickname", "") if isinstance(creator, dict) else "",
            "album": "",
            "cover_url": p.get("coverImgUrl", ""),
            "track_count": p.get("trackCount"),
            "raw": p,
        })
        if len(result) >= limit:
            break
    return result


async def get_subscribed_albums(
    cookies: dict[str, str],
    limit: int = 100,
) -> list[dict]:
    """获取用户收藏的专辑（网易云音乐库）。"""
    payload, _ = await weapi_post(
        "/album/sublist",
        {"limit": min(limit, 200), "offset": 0, "total": True},
        cookies=cookies,
    )
    albums = payload.get("data", []) or []
    result = []
    for a in albums:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        artists = a.get("artists", [])
        artist_names = "、".join(
            [x.get("name", "") for x in artists if isinstance(x, dict)]
        )
        result.append({
            "netease_id": str(a.get("id", "")),
            "title": a.get("name", ""),
            "artist": artist_names,
            "album": a.get("name", ""),
            "cover_url": a.get("picUrl", ""),
            "publish_time": a.get("publishTime"),
            "track_count": a.get("size"),
            "raw": a,
        })
    return result


async def get_song_url(
    cookies: dict[str, str],
    song_id: str,
    br: int = 128000,
) -> str | None:
    """获取歌曲试听音频 URL（weapi /song/enhance/player/url，30s 试听）。

    非 VIP 歌曲可返回标准音质试听链接；失败时兜底网易云外链播放器。
    """
    payload, _ = await weapi_post(
        "/song/enhance/player/url",
        {"ids": f"[{song_id}]", "br": br},
        cookies=cookies,
    )
    data = payload.get("data") or []
    if isinstance(data, list) and data:
        url = (data[0].get("url") or "").strip()
        if url:
            return url
    # 兜底：网易云外链播放器（30s 预览，无需登录）
    return f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"


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
