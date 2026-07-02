"""歌曲管理路由：列表、详情、收藏。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.song import Song
from app.models.user import User, UserFavorite
from app.schemas.song import FavoriteOut, SongListOut, SongOut

router = APIRouter(prefix="/api/songs", tags=["歌曲"])


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
    items = [SongOut.model_validate(s) for s in result.scalars().all()]
    return SongListOut(total=total, items=items)


@router.get("/{song_id}", response_model=SongOut)
async def get_song(song_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    return SongOut.model_validate(song)


@router.post("/{song_id}/favorite", response_model=FavoriteOut)
async def add_favorite(
    song_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    song = await db.execute(select(Song).where(Song.id == song_id))
    if not song.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="歌曲不存在")

    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == user.id,
            UserFavorite.song_id == song_id,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(UserFavorite(user_id=user.id, song_id=song_id))
    return FavoriteOut(song_id=song_id, favorited=True)


@router.delete("/{song_id}/favorite", response_model=FavoriteOut)
async def remove_favorite(
    song_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == user.id,
            UserFavorite.song_id == song_id,
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        await db.delete(fav)
    return FavoriteOut(song_id=song_id, favorited=False)
