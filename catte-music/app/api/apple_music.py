"""Apple Music 路由。"""
from __future__ import annotations

import logging

import asyncio

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.song import Song
from app.models.user import User
from app.services.apple_music.client import AppleMusicClient

router = APIRouter(prefix="/api/apple-music", tags=["Apple Music"])
logger = logging.getLogger(__name__)

# 知名艺术家简介
ARTIST_BIOS: dict[str, str] = {
    "hoyomix": "HOYO-MiX是米哈游旗下原创音乐团队，为《原神》《崩坏》系列创作了数百首融合交响乐与民族元素的配乐。",
    "genshin impact": "《原神》由HOYO-MiX创作原声，以管弦乐为核心融入世界民族乐器，被Apple Music多次收录编辑精选歌单。",
    "周深": "周深，中国内地流行男歌手，以空灵惊艳的嗓音和超广音域闻名，代表作《大鱼》《光亮》。",
    "洛天依": "洛天依是世界首位中文VOCALOID虚拟歌手，Vsinger旗下，声音以治愈甜美著称。",
    "张杰": "张杰，中国内地流行男歌手，以高亢嗓音和现场爆发力著称，代表作《逆战》《这就是爱》。",
    "林俊杰": "林俊杰，新加坡华语流行歌手/音乐制作人，以独特嗓音和钢琴创作为特色，代表作《江南》《修炼爱情》。",
    "邓紫棋": "邓紫棋，香港创作型女歌手，以高音爆发力和自创作品闻名，代表作《光年之外》《泡沫》。",
    "周杰伦": "周杰伦，华语流行天王，R&B与中国风融合开创者，代表作《七里香》《夜曲》《青花瓷》。",
    "陈奕迅": "陈奕迅，香港实力派男歌手，以深情嗓音和完美演唱技巧称霸华语乐坛。",
    "taylor swift": "Taylor Swift，美国创作型女歌手，从乡村到流行音乐的标志性转型代表，Billboard 多次年度艺人。",
    "ed sheeran": "Ed Sheeran，英国创作型男歌手，以吉他弹奏和真挚歌词闻名，代表作《Shape of You》《Perfect》。",
}


async def _background_enrich(song_ids: list[int]) -> None:
    """后台任务：为新同步的歌曲采集 B 站风格数据 + Apple Music 元数据。"""
    from app.database import async_session_factory
    from app.services.feedback import collect_external_feedback
    from app.services.enrich import enrich_song
    from app.models.song import Song
    from sqlalchemy import select

    async with async_session_factory() as bg_db:
        for song_id in song_ids:
            try:
                result = await bg_db.execute(select(Song).where(Song.id == song_id))
                song = result.scalar_one_or_none()
                # Apple Music 歌曲才做 catalog 增强；网易云歌曲跳过
                if song and getattr(song, "platform", "apple") == "apple":
                    await enrich_song(bg_db, song, enrich_album=True)
                    await bg_db.commit()
            except Exception:
                pass

            try:
                await collect_external_feedback(bg_db, song_id, force=True)
                await bg_db.commit()
            except Exception:
                pass

            await asyncio.sleep(1.5)  # B 站请求间隔


async def _get_client(user: User) -> AppleMusicClient:
    if not user.apple_music_token:
        raise HTTPException(
            status_code=400, detail="请先在首页点击「同步 Apple Music 听歌记录」完成授权"
        )
    return AppleMusicClient(
        music_user_token=user.apple_music_token,
    )


async def _ensure_song_in_db(
    db: AsyncSession, apple_music_id: str, title: str, artist: str,
    album: str = "", duration_ms: int | None = None,
    raw_meta: dict | None = None, song_type: str = "song",
    user_id: int | None = None,
) -> Song:
    """拉取的歌曲/专辑自动入库，补全缺失的元数据 + 艺术家简介。

    按 (user_id, apple_music_id) 去重：不同用户各自维护一份记录。
    """
    query = select(Song).where(Song.apple_music_id == apple_music_id)
    if user_id is not None:
        query = query.where(Song.user_id == user_id)
    result = await db.execute(query)
    song = result.scalar_one_or_none()
    if song:
        if raw_meta and not song.raw_meta:
            song.raw_meta = raw_meta
        if album and not song.album:
            song.album = album
        if duration_ms and not song.duration_ms:
            song.duration_ms = duration_ms
        if not getattr(song, "type", None):
            song.type = song_type
        if not getattr(song, "artist_bio", None):
            song.artist_bio = _get_artist_bio(artist)
        return song
    song = Song(
        apple_music_id=apple_music_id, title=title, artist=artist,
        album=album or None, duration_ms=duration_ms, raw_meta=raw_meta,
        type=song_type, artist_bio=_get_artist_bio(artist), user_id=user_id,
    )
    db.add(song)
    await db.flush()
    return song


def _get_artist_bio(artist: str) -> str | None:
    """匹配知名艺术家简介。"""
    lower = artist.lower()
    for key, bio in ARTIST_BIOS.items():
        if key in lower:
            return bio
    return f"{artist} 的音乐人。"


@router.get("/recent")
async def recent_played(
    limit: int = Query(20, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """同步最近播放记录（歌曲 + 专辑均入库）+ 后台采集外部风格数据。"""
    client = await _get_client(user)
    data = await client.get_recent_played(limit=limit)

    songs = []
    new_song_ids: list[int] = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        item_type = item.get("type", "song")
        preview_url = None
        previews = attrs.get("previews", [])
        if previews:
            preview_url = previews[0].get("url")
        song = await _ensure_song_in_db(
            db,
            apple_music_id=item["id"],
            title=attrs.get("name", ""),
            artist=attrs.get("artistName", ""),
            album=attrs.get("albumName", ""),
            duration_ms=attrs.get("durationInMillis"),
            raw_meta=attrs,
            song_type=item_type,
            user_id=user.id,
        )
        songs.append({
            "id": song.id, "apple_music_id": song.apple_music_id,
            "title": song.title, "artist": song.artist,
            "album": song.album, "duration_ms": song.duration_ms,
            "preview_url": preview_url,
            "type": item_type,
            "artist_bio": getattr(song, "artist_bio", None),
        })
        new_song_ids.append(song.id)

    await db.commit()

    # 后台异步采集 B 站风格数据 + Apple Music 元数据增强
    if new_song_ids and background_tasks:
        background_tasks.add_task(_background_enrich, new_song_ids)

    return {"items": songs}


@router.get("/heavy-rotation")
async def heavy_rotation(
    limit: int = Query(10, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client = await _get_client(user)
    data = await client.get_heavy_rotation(limit=limit)
    songs = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        item_type = item.get("type", "song")
        preview_url = None
        previews = attrs.get("previews", [])
        if previews:
            preview_url = previews[0].get("url")
        song = await _ensure_song_in_db(
            db,
            apple_music_id=item["id"],
            title=attrs.get("name", ""),
            artist=attrs.get("artistName", ""),
            album=attrs.get("albumName", ""),
            duration_ms=attrs.get("durationInMillis"),
            raw_meta=attrs,
            song_type=item_type,
        )
        songs.append({
            "id": song.id, "apple_music_id": song.apple_music_id,
            "title": song.title, "artist": song.artist,
            "album": song.album, "preview_url": preview_url,
            "type": item_type,
            "artist_bio": getattr(song, "artist_bio", None),
        })
    return {"items": songs}


@router.post("/rating/{apple_music_id}")
async def rate_song(
    apple_music_id: str,
    rating: int = Query(1, ge=-1, le=1),
    user: User = Depends(get_current_user),
):
    client = await _get_client(user)
    result = await client.rate_song(apple_music_id, rating)
    return result


@router.get("/search")
async def search_apple_music(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=25),
    user: User = Depends(get_current_user),
):
    client = await _get_client(user)
    results = await client.search(q, limit=limit)
    return results