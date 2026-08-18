"""MusicBrainz 音乐元数据查询服务（相对权威的公开曲库）。"""
import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# MusicBrainz 要求标识 User-Agent，否则请求会被拒绝
MB_USER_AGENT = "CatteMusic/1.0 (https://github.com/catteproject)"
MB_BASE = "https://musicbrainz.org/ws/2"
# MusicBrainz 限制 1 req/s，两次请求之间等待
MB_RATE_LIMIT = 1.1


def _clean_title(title: str) -> str:
    """去除标题中的括号注释，如『原神-金律永谐 (游戏《原神》原声音乐)』→『原神-金律永谐』。"""
    return re.sub(r"\s*[（(][^）)]*[）)]", "", title).strip()


async def search_release_groups(title: str, artist: str | None = None, limit: int = 5) -> list[dict]:
    """按 专辑/歌曲名（+ 艺术家）搜索 MusicBrainz release-group。"""
    if artist:
        query = f'release:"{title}" AND artist:"{artist}"'
    else:
        query = f'release:"{title}"'
    params = {
        "query": query,
        "fmt": "json",
        "limit": limit,
        "inc": "tags+ratings",
    }
    headers = {"User-Agent": MB_USER_AGENT}
    async with httpx.AsyncClient(timeout=10.0) as cli:
        for attempt in range(2):
            resp = await cli.get(
                f"{MB_BASE}/release-group", params=params, headers=headers
            )
            if resp.status_code == 503 and attempt == 0:
                await asyncio.sleep(MB_RATE_LIMIT)
                continue
            resp.raise_for_status()
            return resp.json().get("release-groups", [])
    return []


def _clean(rg: dict) -> dict:
    """release-group → 精简展示字段。"""
    artists = "、".join(
        c.get("name", "") for c in rg.get("artist-credit", []) if c.get("name")
    )
    types = [t for t in [rg.get("primary-type") or ""] + (rg.get("secondary-types") or []) if t]
    tags = [t.get("name") for t in (rg.get("tags") or [])[:6] if t.get("name")]
    rating = rg.get("rating") or {}
    mbid = rg.get("id")
    return {
        "mbid": mbid,
        "title": rg.get("title"),
        "artist": artists or None,
        "release_date": rg.get("first-release-date"),
        "type": "/".join(types) if types else None,
        "tags": tags,
        "rating": rating.get("value"),
        "rating_votes": rating.get("votes", 0),
        "track_count": rg.get("count"),
        "url": f"https://musicbrainz.org/release-group/{mbid}" if mbid else None,
    }


async def fetch_musicbrainz_info(title: str, artist: str) -> dict:
    """获取 MusicBrainz 权威元数据；未匹配到时 found=False。

    逐级降级匹配，提高不同平台（Apple Music 中文专辑等）的命中率：
    1. 清洗后的标题 + 艺术家（AND）
    2. 清洗后的标题（仅标题）
    3. 原始标题（仅标题）
    """
    clean = _clean_title(title) or title
    attempts = []
    if clean and clean != title:
        attempts.append((clean, artist))
    attempts.append((clean, artist))
    attempts.append((clean, None))
    if title != clean:
        attempts.append((title, None))

    for t, ar in attempts:
        try:
            groups = await search_release_groups(t, ar)
        except httpx.HTTPError as exc:
            logger.warning("MusicBrainz 搜索失败 title=%s: %s", t, exc)
            groups = []
        if groups:
            return {"found": True, "items": [_clean(rg) for rg in groups[:5]]}
        await asyncio.sleep(MB_RATE_LIMIT)
    return {"found": False, "items": []}
