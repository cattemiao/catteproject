"""歌曲路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.song import Song
from app.models.user import User, UserFavorite
from app.schemas.song import FavoriteOut, SongListOut, SongOut
from app.services.apple_music.auth import API_BASE, get_developer_token
from app.api.analyze import _search_preview

import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/songs", tags=["歌曲"])


def _song_to_out(song: Song) -> SongOut:
    """Song ORM → SongOut，提取预览 URL。"""
    preview_url = None
    if song.raw_meta:
        try:
            previews = song.raw_meta.get("attributes", {}).get("previews", [])
            if previews:
                preview_url = previews[0].get("url")
        except (AttributeError, KeyError):
            pass
    return SongOut(
        id=song.id,
        apple_music_id=song.apple_music_id,
        title=song.title,
        artist=song.artist,
        album=song.album,
        duration_ms=song.duration_ms,
        preview_url=preview_url,
        raw_meta=song.raw_meta,
        type=getattr(song, "type", "song") or "song",
        artist_bio=getattr(song, "artist_bio", None),
    )


@router.get("", response_model=SongListOut)
async def list_songs(
    q: str | None = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Song)
    count_query = select(func.count()).select_from(Song)

    if q:
        query = query.where(Song.title.ilike(f"%{q}%") | Song.artist.ilike(f"%{q}%"))
        count_query = count_query.where(
            Song.title.ilike(f"%{q}%") | Song.artist.ilike(f"%{q}%")
        )

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(Song.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = [_song_to_out(s) for s in result.scalars().all()]
    return SongListOut(total=total, items=items)


@router.get("/{song_id}", response_model=SongOut)
async def get_song(song_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    return _song_to_out(song)


@router.get("/{song_id}/preview")
async def get_song_preview(song_id: int, db: AsyncSession = Depends(get_db)):
    """获取歌曲的 Apple Music 预览音频 URL（实时搜索）。"""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    try:
        url = await _search_preview(song.title, song.artist)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Apple Music 搜索失败")
    if not url:
        raise HTTPException(status_code=404, detail="未找到预览音频")
    return {"preview_url": url, "title": song.title, "artist": song.artist}


@router.get("/{song_id}/review")
async def get_song_review(song_id: int, db: AsyncSession = Depends(get_db)):
    """获取歌曲评价（优先 Apple Music editorial notes，降级为基本信息描述）。"""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")

    # 尝试从 raw_meta 提取 editorial notes
    editorial = None
    if song.raw_meta:
        editorial = (
            song.raw_meta.get("editorialNotes", {})
            .get("standard", "")
            or song.raw_meta.get("editorialNotes", {})
            .get("short", "")
        )
    if editorial:
        return {
            "source": "Apple Music Editorial",
            "review": editorial,
        }

    # 降级：基本信息描述
    desc_parts = [f"{song.artist} 的作品"]
    if song.album:
        desc_parts.append(f"收录于专辑《{song.album}》")
    if song.duration_ms:
        mins = song.duration_ms // 60000
        secs = (song.duration_ms % 60000) // 1000
        desc_parts.append(f"时长 {mins}:{secs:02d}")
    return {
        "source": "基本信息",
        "review": "，".join(desc_parts) + "。",
    }


@router.get("/{song_id}/album-tracks")
async def get_album_tracks(song_id: int, db: AsyncSession = Depends(get_db)):
    """如果歌曲是专辑类型，从 Apple Music catalog 拉取曲目列表。"""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    if getattr(song, "type", "song") != "albums":
        raise HTTPException(status_code=400, detail="该条目不是专辑")

    dev_token = get_developer_token()
    headers = {"Authorization": f"Bearer {dev_token}"}
    async with httpx.AsyncClient(timeout=15.0) as cli:
        resp = await cli.get(
            f"{API_BASE}/v1/catalog/us/albums/{song.apple_music_id}/tracks",
            params={"limit": 50},
            headers=headers,
        )
        resp.raise_for_status()
    data = resp.json()
    tracks = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        previews = attrs.get("previews", [])
        tracks.append({
            "id": item["id"],
            "title": attrs.get("name", ""),
            "artist": attrs.get("artistName", ""),
            "duration_ms": attrs.get("durationInMillis"),
            "track_number": attrs.get("trackNumber"),
            "preview_url": previews[0]["url"] if previews else None,
        })
    return {"album_title": song.title, "album_artist": song.artist, "tracks": tracks}


@router.post("/{song_id}/favorite", response_model=FavoriteOut)
async def favorite_song(
    song_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Song).where(Song.id == song_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="歌曲不存在")
    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == user.id, UserFavorite.song_id == song_id
        )
    )
    if existing.scalar_one_or_none():
        return FavoriteOut(user_id=user.id, song_id=song_id, created_at="")
    fav = UserFavorite(user_id=user.id, song_id=song_id)
    db.add(fav)
    await db.commit()
    return FavoriteOut(user_id=user.id, song_id=song_id, created_at=str(fav.created_at))