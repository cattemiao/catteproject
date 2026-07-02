"""AI 音乐推荐：基于情绪标签与内容的推荐。"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.song import Song, SongEmotion, SongTag, Tag
from app.models.user import Emotion, UserFavorite

logger = logging.getLogger(__name__)


async def recommend_by_emotion(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[Song]:
    """基于用户收藏歌曲的情绪偏好推荐相似歌曲。

    策略：
    1. 找到用户收藏歌曲的 Top 情绪
    2. 推荐同情绪下用户未收藏的其他歌曲
    """
    # 1. 查用户收藏歌曲的情绪分布
    user_emotions = await db.execute(
        select(SongEmotion.emotion_id, Emotion.name)
        .join(UserFavorite, UserFavorite.song_id == SongEmotion.song_id)
        .join(Emotion, Emotion.id == SongEmotion.emotion_id)
        .where(UserFavorite.user_id == user_id)
    )
    emotion_rows = user_emotions.fetchall()

    if not emotion_rows:
        # 无收藏数据时返回热门（按 id 倒序）
        result = await db.execute(select(Song).order_by(Song.id.desc()).limit(limit))
        return list(result.scalars().all())

    top_emotion_id = emotion_rows[0][0]

    # 2. 查同情绪下未收藏的歌曲
    favorited_ids_sq = (
        select(UserFavorite.song_id).where(UserFavorite.user_id == user_id)
    ).subquery()

    result = await db.execute(
        select(Song)
        .join(SongEmotion, SongEmotion.song_id == Song.id)
        .where(
            SongEmotion.emotion_id == top_emotion_id,
            Song.id.not_in(favorited_ids_sq),
        )
        .limit(limit)
    )
    return list(result.scalars().all())
