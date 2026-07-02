"""Apple Music 数据路由：最近播放、打分等。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.song import Song
from app.models.user import User
from app.services.apple_music.client import AppleMusicClient

router = APIRouter(prefix="/api/apple-music", tags=["Apple Music"])


async def _get_client(user: User) -> AppleMusicClient:
    if not user.apple_music_token:
        raise HTTPException(status_code=400, detail="请先授权 Apple Music")
    return AppleMusicClient(music_user_token=user.apple_music_token)


async def _ensure_song_in_db(
    db: AsyncSession, apple_music_id: str, title: str, artist: str
) -> Song:
    """拉取的歌曲自动入库（去重 by apple_music_id）。"""
    result = await db.execute(
        select(Song).where(Song.apple_music_id == apple_music_id)
    )
    song = result.scalar_one_or_none()
    if song:
        return song
    song = Song(
        apple_music_id=apple_music_id, title=title, artist=artist
    )
    db.add(song)
    await db.flush()
    return song


@router.get("/recent")
async def recent_played(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client = await _get_client(user)
    data = await client.get_recent_played(limit=limit)

    songs = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        song = await _ensure_song_in_db(
            db,
            apple_music_id=item["id"],
            title=attrs.get("name", ""),
            artist=attrs.get("artistName", ""),
        )
        songs.append({"id": song.id, "apple_music_id": song.apple_music_id, "title": song.title, "artist": song.artist})
    return {"items": songs}


@router.get("/heavy-rotation")
async def heavy_rotation(
    user: User = Depends(get_current_user),
):
    client = await _get_client(user)
    return await client.get_heavy_rotation()


@router.post("/rating/{song_apple_id}")
async def rate_song(
    song_apple_id: str,
    rating: int,
    user: User = Depends(get_current_user),
):
    if rating not in (-1, 0, 1):
        raise HTTPException(status_code=400, detail="rating 必须为 -1, 0 或 1")
    client = await _get_client(user)
    return await client.rate_song(song_apple_id, rating)
