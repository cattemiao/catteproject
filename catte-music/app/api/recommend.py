"""推荐路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.songs import _song_to_out
from app.database import get_db
from app.models.user import User
from app.schemas.song import SongOut
from app.services.recommend import recommend_by_emotion

router = APIRouter(prefix="/api", tags=["推荐"])


@router.get("/recommend", response_model=list[SongOut])
async def recommend(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    songs = await recommend_by_emotion(db, user.id, limit=limit)
    return [_song_to_out(s) for s in songs]
