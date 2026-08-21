"""AI 音乐推荐：情绪标签/风格推荐 + 社区分享推荐流水线。"""
from __future__ import annotations

import logging
import math
import random
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.share import Like, Share
from app.models.song import Song, SongEmotion, SongTag, Tag
from app.models.prediction import AiPrediction
from app.models.user import Emotion, User, UserFavorite

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
    platform: str | None = None,
) -> list[Song]:
    """基于用户收藏歌曲的情绪偏好推荐相似歌曲。

    策略：
    1. 找到用户收藏歌曲的 Top 情绪
    2. 推荐同情绪下用户未收藏的其他歌曲（仅限该用户自己的歌曲，可选按平台过滤）
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
        # 无收藏数据时返回该用户最近同步的歌曲
        query = select(Song).where(Song.user_id == user_id)
        if platform:
            query = query.where(Song.platform == platform)
        result = await db.execute(query.order_by(Song.id.desc()).limit(limit))
        return list(result.scalars().all())

    top_emotion_id = emotion_rows[0][0]

    # 2. 查同情绪下未收藏的歌曲
    favorited_ids_sq = (
        select(UserFavorite.song_id).where(UserFavorite.user_id == user_id)
    ).subquery()

    query = (
        select(Song)
        .join(SongEmotion, SongEmotion.song_id == Song.id)
        .where(
            SongEmotion.emotion_id == top_emotion_id,
            Song.user_id == user_id,  # 仅推荐该用户自己的歌曲
            Song.id.not_in(favorited_ids_sq),
        )
    )
    if platform:
        query = query.where(Song.platform == platform)
    result = await db.execute(query.limit(limit))
    return list(result.scalars().all())


async def recommend_by_style(
    db: AsyncSession,
    user_id: int,
    limit: int = 6,
    platform: str | None = None,
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
        # 无收藏：返回该用户最近同步的歌曲
        query = select(Song).where(Song.user_id == user_id)
        if platform:
            query = query.where(Song.platform == platform)
        result = await db.execute(query.order_by(Song.id.desc()).limit(limit))
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
        # 无流派也无情绪信息，降级到该用户最新
        query = (
            select(Song)
            .where(Song.user_id == user_id)
            .where(~Song.id.in_(fav_ids) if fav_ids else True)
        )
        if platform:
            query = query.where(Song.platform == platform)
        result = await db.execute(query.order_by(Song.id.desc()).limit(limit))
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

    # 4. 从库内找候选（该用户未收藏的歌曲，可选按平台过滤）
    cand_query = (
        select(Song)
        .where(Song.user_id == user_id)
        .where(~Song.id.in_(fav_ids) if fav_ids else True)
    )
    if platform:
        cand_query = cand_query.where(Song.platform == platform)
    cand_result = await db.execute(cand_query)
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


# ---------------------------------------------------------------------------
# 社区分享推荐流水线：平台过滤 → 情绪相似度排序 → 点赞加权 → 随机兜底补足
# ---------------------------------------------------------------------------

_DIMENSION_FIELDS = ("loudness", "high_freq", "rhythm", "soundstage", "layering", "soothing", "prosody")


def _cosine_sim(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    """两个同维向量的余弦相似度（兼容 7 维声学与 20 维情绪向量）。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _emotion_vector(pred: AiPrediction) -> np.ndarray | None:
    """pred → 20 维情绪分布向量（按 EMOTION_LABELS 顺序）。

    优先取 v2 的 emotion_probs；旧数据（NULL）用存储的特征向量重建
    模板伪概率补齐，保证推荐相似度对新旧数据一致。
    """
    from app.services.ai import model as ai_model
    from app.services.ai.feature import template_probs

    if pred.emotion_probs:
        return ai_model.probs_vector(pred.emotion_probs)
    fv = pred.feature_vector
    if not fv:
        return None
    try:
        keys = sorted(fv, key=lambda k: int(k))
        vec = [float(fv[k]) for k in keys]
        return ai_model.probs_vector(template_probs(np.array(vec)))
    except (ValueError, TypeError):
        return None


async def _user_avg_profiles(
    db: AsyncSession, user_id: int
) -> tuple[np.ndarray | None, list[float] | None]:
    """聚合用户所有 AI 分析结果的平均 20 维情绪向量 + 平均 7 维声学向量。

    每首歌只取最新一条预测；均无有效数据返回 (None, None)。
    """
    song_ids = (
        await db.execute(select(Song.id).where(Song.user_id == user_id))
    ).scalars().all()
    if not song_ids:
        return None, None
    preds = (
        await db.execute(
            select(AiPrediction)
            .where(AiPrediction.song_id.in_(song_ids))
            .order_by(AiPrediction.id.desc())
        )
    ).scalars().all()

    seen: set[int] = set()
    emotion_vecs: list[np.ndarray] = []
    acoustic_vecs: list[list[float]] = []
    for p in preds:  # 每首歌只取最新一条预测
        if p.song_id in seen:
            continue
        seen.add(p.song_id)
        ev = _emotion_vector(p)
        if ev is not None:
            emotion_vecs.append(ev)
        ac = [getattr(p, f) for f in _DIMENSION_FIELDS]
        if all(v is not None for v in ac):
            acoustic_vecs.append(ac)

    if not emotion_vecs and not acoustic_vecs:
        return None, None
    avg_emotion = None
    if emotion_vecs:
        avg_emotion = np.mean(np.stack(emotion_vecs), axis=0)
    avg_acoustic = None
    if acoustic_vecs:
        avg_acoustic = [sum(col) / len(col) for col in zip(*acoustic_vecs)]
    return avg_emotion, avg_acoustic


async def _latest_profiles(
    db: AsyncSession, song_ids: list[int]
) -> dict[int, tuple[np.ndarray | None, list[float] | None, str | None]]:
    """批量取多首歌最新 AI 预测的 (20 维情绪向量, 7 维声学向量, 情绪名)。

    Returns:
        {song_id: (emotion_vec | None, acoustic_vec | None, emotion_name | None)}
    """
    result: dict[int, tuple[np.ndarray | None, list[float] | None, str | None]] = {}
    if not song_ids:
        return result
    preds = (
        await db.execute(
            select(AiPrediction, Emotion.name)
            .join(Emotion, Emotion.id == AiPrediction.emotion_id)
            .where(AiPrediction.song_id.in_(song_ids))
            .order_by(AiPrediction.id.desc())
        )
    ).all()
    for p, emotion_name in preds:  # 按 id 倒序，首个即最新
        if p.song_id in result:
            continue
        ac = [getattr(p, f) for f in _DIMENSION_FIELDS]
        acoustic = ac if all(v is not None for v in ac) else None
        result[p.song_id] = (_emotion_vector(p), acoustic, emotion_name)
    return result


async def recommend_shares(
    db: AsyncSession,
    user: User,
    limit: int = 20,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    """社区分享推荐：完全来自其他用户的分享。

    流水线：
    1. **平台过滤**：分享来源必须与请求界面一致（Apple 界面只推 apple，网易云页只推 netease）。
       已绑定用户按其绑定平台过滤；未绑定任何平台时按请求的平台过滤；绑定了其他平台但
       未绑定请求的平台时返回空（该界面无对应来源内容）。
    2. **情绪相似度**：聚合用户 AI 分析的平均 7 维向量，与各分享歌曲向量算余弦相似度。
    3. **点赞加权**：相似度基础上按点赞数加权（越多越靠前）。
    4. **随机兜底**：不足 limit 时用剩余分享随机补足，保证列表长度。

    Returns:
        list of {
            "share": Share, "song": Song, "sharer": User,
            "like_count": int, "user_liked": bool,
            "emotion": str | None, "similarity": float | None,
        }
    """
    # 1. 平台过滤：分享来源与请求界面保持一致
    bound: list[str] = []
    if user.apple_music_token:
        bound.append("apple")
    if user.netease_cookie:
        bound.append("netease")
    if platform:
        if platform in bound:
            bound = [platform]
        elif not bound:
            # 未绑定任何平台：按请求的平台过滤，保证界面来源一致
            bound = [platform]
        else:
            # 绑定了其他平台但未绑定请求的平台：该界面无对应来源的分享
            return []

    like_count_sq = (
        select(Like.share_id, func.count(Like.id).label("cnt"))
        .group_by(Like.share_id)
        .subquery()
    )
    where = [Share.user_id != user.id]
    if bound:
        where.append(Share.platform.in_(bound))
    rows = (
        await db.execute(
            select(Share, Song, User, like_count_sq.c.cnt.label("like_count"))
            .join(Song, Song.id == Share.song_id)
            .where(*where)
            .join(User, User.id == Share.user_id)
            .outerjoin(like_count_sq, like_count_sq.c.share_id == Share.id)
            .order_by(Share.id.desc())
            .limit(500)  # 上限保护：全量分享再排序
        )
    ).all()

    if not rows:
        return []

    # 已赞集合（当前用户）
    liked_ids = set(
        (
            await db.execute(
                select(Like.share_id).where(Like.user_id == user.id, Like.share_id.in_([r[0].id for r in rows]))
            )
        ).scalars().all()
    )

    # 2. 情绪相似度：20 维情绪分布余弦 ×0.7 + 7 维声学余弦 ×0.3
    avg_emotion, avg_acoustic = await _user_avg_profiles(db, user.id)
    pred_map = await _latest_profiles(db, [r[1].id for r in rows])

    scored: list[tuple[float, dict[str, Any]]] = []
    for share, song, sharer, like_count in rows:
        like_count = like_count or 0
        emo_vec, ac_vec, emotion_name = pred_map.get(song.id, (None, None, None))
        emotion_sim = (
            _cosine_sim(avg_emotion, emo_vec)
            if avg_emotion is not None and emo_vec is not None
            else 0.0
        )
        acoustic_sim = (
            _cosine_sim(avg_acoustic, ac_vec)
            if avg_acoustic is not None and ac_vec is not None
            else 0.0
        )
        sim = 0.7 * emotion_sim + 0.3 * acoustic_sim
        # 3. 点赞加权：相似度 + 点赞带来的加分（封顶避免刷票）
        score = sim + min(like_count, 50) * 0.02
        scored.append(
            (
                score,
                {
                    "share": share,
                    "song": song,
                    "sharer": sharer,
                    "like_count": like_count,
                    "user_liked": share.id in liked_ids,
                    "emotion": emotion_name,
                    "similarity": (
                        round(sim, 4)
                        if (avg_emotion is not None or avg_acoustic is not None)
                        else None
                    ),
                },
            )
        )

    # 相似度优先，点赞加权已并入 score
    scored.sort(key=lambda x: -x[0])

    # 4. 随机兜底：不足 limit 时用剩余分享随机补足（打乱后补充）
    ranked = [item for _, item in scored]
    if len(ranked) > limit:
        top = ranked[:limit]
        rest = ranked[limit:]
        random.shuffle(rest)
        ranked = top + rest
    else:
        random.shuffle(ranked)

    return ranked[:limit]
