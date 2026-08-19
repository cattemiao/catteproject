"""管理后台路由：用户管理与意见管理。

仅 ADMIN_USERNAME / ADMIN_PASSWORD（来自 .env）登录的管理员可访问，
通过 `get_current_admin` 依赖鉴权。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.database import get_db
from app.models.pageview import PageView
from app.models.prediction import AiPrediction
from app.models.share import Like, Share
from app.models.song import Song, SongEmotion, SongTag
from app.models.suggestion import Suggestion
from app.models.user import Emotion, User, UserFavorite
from app.utils.security import hash_password

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


# ───────────────────────── 用户管理 ─────────────────────────


class AdminUserOut(BaseModel):
    id: int
    username: str
    has_apple_music: bool
    has_netease: bool
    song_count: int
    favorite_count: int
    suggestion_count: int
    created_at: str


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出所有注册用户及其资源统计。"""
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()

    song_counts = dict(
        (
            await db.execute(
                select(Song.user_id, func.count()).group_by(Song.user_id)
            )
        ).all()
    )
    fav_counts = dict(
        (
            await db.execute(
                select(UserFavorite.user_id, func.count()).group_by(UserFavorite.user_id)
            )
        ).all()
    )
    sug_counts = dict(
        (
            await db.execute(
                select(Suggestion.user_id, func.count()).group_by(Suggestion.user_id)
            )
        ).all()
    )

    return [
        AdminUserOut(
            id=u.id,
            username=u.username,
            has_apple_music=bool(u.apple_music_token),
            has_netease=bool(u.netease_cookie),
            song_count=song_counts.get(u.id, 0),
            favorite_count=fav_counts.get(u.id, 0),
            suggestion_count=sug_counts.get(u.id, 0),
            created_at=u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
        )
        for u in users
    ]


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除用户，并级联清理其全部关联数据（歌曲、预测、情绪、标签、收藏）。"""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 该用户同步的歌曲
    song_ids = list(
        (
            await db.execute(select(Song.id).where(Song.user_id == user_id))
        ).scalars().all()
    )

    if song_ids:
        # 歌曲的关联数据（含其他用户收藏了这些歌曲的记录）
        await db.execute(delete(AiPrediction).where(AiPrediction.song_id.in_(song_ids)))
        await db.execute(delete(SongEmotion).where(SongEmotion.song_id.in_(song_ids)))
        await db.execute(delete(SongTag).where(SongTag.song_id.in_(song_ids)))
        await db.execute(delete(UserFavorite).where(UserFavorite.song_id.in_(song_ids)))
        await db.execute(delete(Song).where(Song.id.in_(song_ids)))

    # 该用户收藏的他人歌曲
    await db.execute(delete(UserFavorite).where(UserFavorite.user_id == user_id))

    # 意见：保留内容，仅解除与已删除用户的关联
    await db.execute(
        update(Suggestion).where(Suggestion.user_id == user_id).values(user_id=None)
    )

    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    return {"deleted": user_id, "username": user.username, "songs": len(song_ids)}


class ResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    payload: ResetPasswordIn,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """重置指定用户的登录密码。"""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return {"ok": True, "username": user.username}


# ───────────────────────── 意见管理 ─────────────────────────


class AdminSuggestionOut(BaseModel):
    id: int
    user_id: int | None
    username: str
    content: str
    created_at: str


@router.get("/suggestions", response_model=list[AdminSuggestionOut])
async def list_suggestions(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出所有用户提交的意见。"""
    rows = (
        await db.execute(
            select(Suggestion).order_by(Suggestion.id.desc())
        )
    ).scalars().all()
    return [
        AdminSuggestionOut(
            id=r.id,
            user_id=r.user_id,
            username=r.username,
            content=r.content,
            created_at=r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        )
        for r in rows
    ]


class SuggestionUpdateIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


@router.patch("/suggestions/{suggestion_id}", response_model=AdminSuggestionOut)
async def update_suggestion(
    suggestion_id: int,
    payload: SuggestionUpdateIn,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """修改意见内容。"""
    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if not sug:
        raise HTTPException(status_code=404, detail="意见不存在")

    sug.content = payload.content.strip()
    await db.commit()
    return AdminSuggestionOut(
        id=sug.id,
        user_id=sug.user_id,
        username=sug.username,
        content=sug.content,
        created_at=sug.created_at.strftime("%Y-%m-%d %H:%M") if sug.created_at else "",
    )


@router.delete("/suggestions/{suggestion_id}")
async def delete_suggestion(
    suggestion_id: int,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除意见。"""
    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if not sug:
        raise HTTPException(status_code=404, detail="意见不存在")

    await db.execute(delete(Suggestion).where(Suggestion.id == suggestion_id))
    await db.commit()
    return {"deleted": suggestion_id}


# ───────────────────────── Dashboard 统计 ─────────────────────────

_DAYS = 14


def _fill_daily(start: datetime, rows: list[tuple]) -> list[dict]:
    """将查询结果按日期补齐为连续 14 天的序列。"""
    counts = {str(d): c for d, c in rows}
    return [
        {
            "date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
            "count": counts.get((start + timedelta(days=i)).strftime("%Y-%m-%d"), 0),
        }
        for i in range(_DAYS)
    ]


@router.get("/stats/dashboard")
async def dashboard_stats(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理后台 Dashboard 聚合统计。"""
    today = datetime.now()
    start = today - timedelta(days=_DAYS - 1)

    # 总量卡片
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    total_songs = (await db.execute(select(func.count()).select_from(Song))).scalar() or 0
    total_analyses = (
        await db.execute(select(func.count()).select_from(AiPrediction))
    ).scalar() or 0
    total_visits = (await db.execute(select(func.count()).select_from(PageView))).scalar() or 0
    total_shares = (await db.execute(select(func.count()).select_from(Share))).scalar() or 0
    total_likes = (await db.execute(select(func.count()).select_from(Like))).scalar() or 0

    # 近 14 天访问量
    visit_rows = (
        await db.execute(
            select(func.date(PageView.visited_at), func.count())
            .where(func.date(PageView.visited_at) >= start.strftime("%Y-%m-%d"))
            .group_by(func.date(PageView.visited_at))
        )
    ).all()

    # 近 14 天 AI 分析量
    analysis_rows = (
        await db.execute(
            select(func.date(AiPrediction.predicted_at), func.count())
            .where(func.date(AiPrediction.predicted_at) >= start.strftime("%Y-%m-%d"))
            .group_by(func.date(AiPrediction.predicted_at))
        )
    ).all()

    # 近 14 天分享量
    share_rows = (
        await db.execute(
            select(func.date(Share.created_at), func.count())
            .where(func.date(Share.created_at) >= start.strftime("%Y-%m-%d"))
            .group_by(func.date(Share.created_at))
        )
    ).all()

    # 近 14 天点赞量
    like_rows = (
        await db.execute(
            select(func.date(Like.created_at), func.count())
            .where(func.date(Like.created_at) >= start.strftime("%Y-%m-%d"))
            .group_by(func.date(Like.created_at))
        )
    ).all()

    # 歌曲按 平台 + 类型 分布
    song_rows = (
        await db.execute(
            select(Song.platform, Song.type, func.count())
            .group_by(Song.platform, Song.type)
        )
    ).all()
    songs_by_platform = [
        {
            "platform": p or "unknown",
            "type": t or "unknown",
            "count": c,
        }
        for p, t, c in song_rows
    ]

    # 情绪分析结果分布（按情绪分类）
    emotion_rows = (
        await db.execute(
            select(Emotion.name, Emotion.color, func.count(AiPrediction.id))
            .join(AiPrediction, AiPrediction.emotion_id == Emotion.id)
            .group_by(Emotion.id, Emotion.name, Emotion.color)
            .order_by(func.count(AiPrediction.id).desc())
        )
    ).all()
    emotion_distribution = [
        {"name": name, "color": color or "#a855f7", "count": count}
        for name, color, count in emotion_rows
    ]

    # 情绪七维指标（响度/高频/节奏/声场/层次/舒缓/韵律）平均分
    dim_cols = [
        "loudness",
        "high_freq",
        "rhythm",
        "soundstage",
        "layering",
        "soothing",
        "prosody",
    ]
    avgs = (
        await db.execute(select(*[func.avg(getattr(AiPrediction, c)) for c in dim_cols]))
    ).one()
    emotion_dimensions = [
        {
            "dimension": col,
            "avg": round(float(avg), 1) if avg is not None else 0.0,
            "count": (
                await db.execute(
                    select(func.count()).where(
                        getattr(AiPrediction, col).is_not(None)
                    )
                )
            ).scalar()
            or 0,
        }
        for col, avg in zip(dim_cols, avgs)
    ]

    return {
        "total_users": total_users,
        "total_songs": total_songs,
        "total_analyses": total_analyses,
        "total_visits": total_visits,
        "total_shares": total_shares,
        "total_likes": total_likes,
        "visits_by_day": _fill_daily(start, visit_rows),
        "analysis_by_day": _fill_daily(start, analysis_rows),
        "shares_by_day": _fill_daily(start, share_rows),
        "likes_by_day": _fill_daily(start, like_rows),
        "songs_by_platform": songs_by_platform,
        "emotion_distribution": emotion_distribution,
        "emotion_dimensions": emotion_dimensions,
    }
