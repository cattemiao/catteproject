"""推荐路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.shares import _share_to_out
from app.database import get_db
from app.models.user import User
from app.schemas.share import ShareOut
from app.services.recommend import recommend_by_style, recommend_shares

router = APIRouter(prefix="/api", tags=["推荐"])


@router.get("/recommend", response_model=list[ShareOut])
async def recommend(
    limit: int = Query(20, ge=1, le=100),
    platform: str | None = Query(None, description="apple/netease，按平台过滤"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """社区推荐列表：完全来自其他用户的分享。

    流水线：平台过滤（仅推送已绑定平台的分享）→ 情绪相似度排序（7 维余弦）→
    点赞加权 → 随机兜底补足，保证列表长度。
    """
    items = await recommend_shares(db, user, limit=limit, platform=platform)
    return [
        _share_to_out(
            item["share"],
            item["song"],
            item["sharer"],
            item["like_count"],
            item["user_liked"],
            item["emotion"],
            item["similarity"],
        )
        for item in items
    ]


@router.get("/recommend/style")
async def recommend_style(
    limit: int = Query(6, ge=1, le=50),
    platform: str | None = Query(None, description="apple/netease，按平台过滤"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """根据用户偏爱的音乐风格推荐风格相似的新歌。

    返回推荐歌曲列表 + 用户风格偏好 + 每首歌的推荐理由。
    """
    result = await recommend_by_style(db, user.id, limit=limit, platform=platform)
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
