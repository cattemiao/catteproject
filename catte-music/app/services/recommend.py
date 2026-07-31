"""AI 音乐推荐：基于情绪标签与风格的推荐。"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.song import Song, SongEmotion, SongTag, Tag
from app.models.prediction import AiPrediction
from app.models.user import Emotion, UserFavorite

logger = logging.getLogger(__name__)


def _extract_song_genres(song: Song) -> list[str]:
    """从歌曲 raw_meta 提取流派标签。

    优先取增强后的 _enriched.genres，其次原生 genreNames。
    """
    if not song.raw_meta:
        return []
    # 增强后
    enriched = song.raw_meta.get("_enriched", {})
    if enriched.get("genres"):
        return enriched["genres"]
    # 原生 Apple Music attributes
    return song.raw_meta.get("genreNames", []) or []


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


async def recommend_by_style(
    db: AsyncSession,
    user_id: int,
    limit: int = 6,
) -> dict[str, Any]:
    """根据用户偏爱的音乐风格推荐风格相似的新歌。

    策略：
    1. 从用户收藏歌曲提取流派偏好（Apple Music genreNames）
    2. 同时统计用户偏爱的情绪（AiPrediction）
    3. 从库内找同流派 + 同情绪但未收藏的歌曲
    4. 按流派匹配度 + 情绪匹配度综合评分
    5. 返回推荐歌曲 + 推荐理由（匹配的流派/情绪）

    Returns:
        {
            "preference": {
                "top_genres": [["Pop", 5], ...],
                "top_emotion": "治愈",
                "fav_count": 10,
            },
            "recommendations": [
                {
                    "song": Song,
                    "reason": "匹配流派：Pop、R&B · 情绪：治愈",
                    "matched_genres": ["Pop"],
                    "matched_emotion": "治愈",
                    "score": 8.5,
                }
            ]
        }
    """
    # 1. 查用户收藏歌曲
    fav_result = await db.execute(
        select(Song)
        .join(UserFavorite, UserFavorite.song_id == Song.id)
        .where(UserFavorite.user_id == user_id)
    )
    fav_songs = list(fav_result.scalars().all())

    if not fav_songs:
        # 无收藏：返回最新歌曲
        result = await db.execute(
            select(Song).order_by(Song.id.desc()).limit(limit)
        )
        return {
            "preference": None,
            "recommendations": [
                {
                    "song": s,
                    "reason": "为你挑选的新歌",
                    "matched_genres": [],
                    "matched_emotion": None,
                    "score": 0,
                }
                for s in result.scalars().all()
            ],
        }

    fav_ids = {s.id for s in fav_songs}

    # 2. 统计流派偏好
    genre_count: dict[str, int] = {}
    for s in fav_songs:
        for g in _extract_song_genres(s):
            genre_count[g] = genre_count.get(g, 0) + 1

    # 3. 统计用户偏爱的情绪（从 AiPrediction）
    pred_result = await db.execute(
        select(AiPrediction.song_id, Emotion.name)
        .join(Emotion, Emotion.id == AiPrediction.emotion_id)
        .where(AiPrediction.song_id.in_(fav_ids))
        .order_by(AiPrediction.id.desc())
    )
    # 每首歌只取最新预测
    seen_songs: set[int] = set()
    emotion_count: dict[str, int] = {}
    for song_id, emotion_name in pred_result.fetchall():
        if song_id in seen_songs:
            continue
        seen_songs.add(song_id)
        emotion_count[emotion_name] = emotion_count.get(emotion_name, 0) + 1

    top_emotion = max(emotion_count, key=emotion_count.get) if emotion_count else None

    if not genre_count and not top_emotion:
        # 无流派也无情绪信息，降级到最新
        result = await db.execute(
            select(Song)
            .where(~Song.id.in_(fav_ids) if fav_ids else True)
            .order_by(Song.id.desc())
            .limit(limit)
        )
        return {
            "preference": {"top_genres": [], "top_emotion": None, "fav_count": len(fav_songs)},
            "recommendations": [
                {
                    "song": s,
                    "reason": "为你挑选的新歌",
                    "matched_genres": [],
                    "matched_emotion": None,
                    "score": 0,
                }
                for s in result.scalars().all()
            ],
        }

    # Top 3 流派
    top_genres = sorted(genre_count.items(), key=lambda x: -x[1])[:3]
    preferred_genres = {g for g, _ in top_genres}

    # 4. 从库内找候选（未收藏的歌曲）
    cand_result = await db.execute(
        select(Song).where(~Song.id.in_(fav_ids) if fav_ids else True)
    )
    candidates = list(cand_result.scalars().all())

    # 获取候选歌曲的情绪预测
    cand_pred_result = await db.execute(
        select(AiPrediction.song_id, Emotion.name)
        .join(Emotion, Emotion.id == AiPrediction.emotion_id)
        .where(AiPrediction.song_id.in_([s.id for s in candidates]))
        .order_by(AiPrediction.id.desc())
    )
    cand_emotion: dict[int, str] = {}
    for song_id, emotion_name in cand_pred_result.fetchall():
        if song_id not in cand_emotion:  # 取最新
            cand_emotion[song_id] = emotion_name

    # 5. 评分候选
    scored: list[tuple[Song, float, list[str], str | None]] = []
    for s in candidates:
        s_genres = _extract_song_genres(s)
        matched = [g for g in s_genres if g in preferred_genres]
        if not matched and preferred_genres:
            continue  # 有流派偏好时不匹配则跳过

        # 流派得分：匹配到的流派按用户偏好计数加权
        genre_score = sum(genre_count.get(g, 0) for g in matched) if matched else 0

        # 情绪得分
        s_emotion = cand_emotion.get(s.id)
        emotion_score = 0
        if top_emotion and s_emotion == top_emotion:
            emotion_score = emotion_count.get(top_emotion, 0) * 0.5

        total_score = genre_score + emotion_score
        if total_score <= 0 and preferred_genres:
            continue

        scored.append((s, total_score, matched, s_emotion if s_emotion == top_emotion else None))

    # 按得分排序，不足时补充最新歌曲
    scored.sort(key=lambda x: -x[1])
    recommendations = scored[:limit]

    # 不足补充
    if len(recommendations) < limit:
        recommended_ids = {s.id for s, _, _, _ in recommendations}
        for s in candidates:
            if len(recommendations) >= limit:
                break
            if s.id not in recommended_ids:
                recommendations.append((s, 0, [], None))
                recommended_ids.add(s.id)

    # 构造返回
    rec_data = []
    for s, score, matched, matched_emo in recommendations:
        reason_parts = []
        if matched:
            reason_parts.append("匹配流派：" + "、".join(matched[:2]))
        if matched_emo:
            reason_parts.append(f"情绪：{matched_emo}")
        if not reason_parts:
            reason_parts.append("为你挑选的新歌")
        rec_data.append({
            "song": s,
            "reason": " · ".join(reason_parts),
            "matched_genres": matched,
            "matched_emotion": matched_emo,
            "score": round(score, 2),
        })

    return {
        "preference": {
            "top_genres": [[g, c] for g, c in top_genres],
            "top_emotion": top_emotion,
            "fav_count": len(fav_songs),
        },
        "recommendations": rec_data,
    }
