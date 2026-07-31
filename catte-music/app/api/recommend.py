"""推荐路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.songs import _song_to_out
from app.database import get_db
from app.models.user import User
from app.schemas.song import SongOut
from app.services.recommend import recommend_by_emotion, recommend_by_style

router = APIRouter(prefix="/api", tags=["推荐"])


@router.get("/recommend", response_model=list[SongOut])
async def recommend(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    songs = await recommend_by_emotion(db, user.id, limit=limit)
    return [_song_to_out(s) for s in songs]


@router.get("/recommend/style")
async def recommend_style(
    limit: int = Query(6, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """根据用户偏爱的音乐风格推荐风格相似的新歌。

    返回推荐歌曲列表 + 用户风格偏好 + 每首歌的推荐理由。
    """
    result = await recommend_by_style(db, user.id, limit=limit)
    return {
        "preference": result["preference"],
        "recommendations": [
            {
                "song": _song_to_out(item["song"]),
                "reason": item["reason"],
                "matched_genres": item["matched_genres"],
                "matched_emotion": item["matched_emotion"],
                "score": item["score"],
            }
            for item in result["recommendations"]
        ],
    }
