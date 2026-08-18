"""外部数据反馈与模型持续优化模块。

从 B 站、网易云音乐等多平台采集音乐风格数据，与 AI 情绪预测对比，
多源加权共识，差异 > 40% 时自动纠正情绪标签。
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.song import Song
from app.models.prediction import AiPrediction
from app.models.user import Emotion
from app.services.crawler.bilibili import (
    get_song_external_styles,
    get_song_comment_emotions,
    get_bilibili_comment_consensus,
)
from app.services.crawler.netease import get_netease_consensus
from app.services.enrich import analyze_editorial_sentiment

logger = logging.getLogger(__name__)

# 各数据源权重（总和 1.0）
SOURCE_WEIGHTS = {
    "ai_prediction": 0.30,        # AI 特征分析
    "bilibili_tags": 0.20,        # B站视频标签
    "bilibili_comments": 0.15,    # B站热门评论
    "netease": 0.25,              # 网易云音乐标签+评论
    "editorial": 0.10,            # Apple Music 编辑评价
}

# 自动纠正阈值
AUTO_CORRECT_THRESHOLD = 0.4


async def collect_external_feedback(
    db: AsyncSession,
    song_id: int,
    force: bool = False,
) -> dict[str, Any]:
    """为单首歌曲采集多平台风格反馈数据。

    数据源：
    1. B站视频标签 → 风格/情绪映射
    2. B站热门评论 → 情绪关键词分析（点赞加权）
    3. 网易云音乐 → 用户标签 + 热门评论情绪
    4. Apple Music 编辑评论 → 情感关键词
    5. AI 预测 → 已有分析结果
    """
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        return {"error": "歌曲不存在"}

    title = song.title
    artist = song.artist

    # 并行采集多源数据
    bili_styles, bili_emotions, bili_comments, netease_data = await asyncio.gather(
        get_song_external_styles(title, artist),
        get_song_comment_emotions(title, artist),
        get_bilibili_comment_consensus(title, artist),
        get_netease_consensus(title, artist),
    )

    # Apple Music 编辑评论情感
    editorial_scores: dict[str, float] = {}
    if song.raw_meta:
        enriched = song.raw_meta.get("_enriched", {})
        editorial_text = enriched.get("editorial_notes", "")
        if not editorial_text:
            editorial_text = (
                song.raw_meta.get("editorialNotes", {}).get("standard", "")
                or song.raw_meta.get("editorialNotes", {}).get("short", "")
            )
        if editorial_text:
            editorial_scores = analyze_editorial_sentiment(editorial_text)

    # AI 预测
    ai_prediction = await _get_ai_prediction(db, song)

    # 多源加权共识
    consensus = _compute_weighted_consensus(
        ai_prediction=ai_prediction,
        bili_styles=bili_styles,
        bili_comments=bili_comments,
        netease_data=netease_data,
        editorial_scores=editorial_scores,
    )

    # 自动纠正
    correction = await _auto_correct_if_needed(
        db=db,
        song=song,
        ai_prediction=ai_prediction,
        consensus=consensus,
    )

    # 存储结果
    feedback = {
        "sources": {
            "bilibili_styles": bili_styles,
            "bilibili_comments": bili_comments,
            "netease": netease_data,
            "editorial_scores": editorial_scores,
            "ai_prediction": ai_prediction,
        },
        "consensus": consensus,
        "auto_correction": correction,
        "updated_at": datetime.datetime.utcnow().isoformat(),
    }

    if song.raw_meta is None:
        song.raw_meta = {}
    song.raw_meta["_external_feedback"] = feedback
    await db.commit()

    return feedback


async def _get_ai_prediction(db: AsyncSession, song: Song) -> dict | None:
    """获取最新的 AI 预测。"""
    from sqlalchemy.orm import joinedload

    pred_result = await db.execute(
        select(AiPrediction)
        .where(AiPrediction.song_id == song.id)
        .options(joinedload(AiPrediction.emotion_rel))
        .order_by(AiPrediction.id.desc())
        .limit(1)
    )
    pred = pred_result.scalar_one_or_none()
    if pred and pred.emotion_rel:
        return {
            "emotion": pred.emotion_rel.name,
            "confidence": pred.confidence,
        }
    return None


def _compute_weighted_consensus(
    ai_prediction: dict | None,
    bili_styles: dict | None,
    bili_comments: dict | None,
    netease_data: dict | None,
    editorial_scores: dict[str, float] | None,
) -> dict[str, Any]:
    """多源加权共识计算。

    每个数据源返回 {情绪: 置信度}，按权重汇总投票。
    """
    # 收集各源的最高情绪 + 置信度
    source_votes: list[tuple[str, float, float, str]] = []
    # (emotion, confidence, weight, source_label)

    # 1. AI
    if ai_prediction:
        source_votes.append((
            ai_prediction["emotion"],
            ai_prediction["confidence"],
            SOURCE_WEIGHTS["ai_prediction"],
            "AI分析",
        ))

    # 2. B站标签
    if bili_styles and bili_styles.get("primary_style"):
        source_votes.append((
            bili_styles["primary_style"],
            bili_styles.get("confidence", 0),
            SOURCE_WEIGHTS["bilibili_tags"],
            "B站标签",
        ))

    # 3. B站评论
    if bili_comments and bili_comments.get("primary_emotion"):
        source_votes.append((
            bili_comments["primary_emotion"],
            bili_comments.get("confidence", 0),
            SOURCE_WEIGHTS["bilibili_comments"],
            "B站评论",
        ))

    # 4. 网易云
    if netease_data and netease_data.get("primary_emotion") and netease_data.get("has_data"):
        source_votes.append((
            netease_data["primary_emotion"],
            netease_data.get("confidence", 0),
            SOURCE_WEIGHTS["netease"],
            "网易云音乐",
        ))

    # 5. 编辑评论
    if editorial_scores:
        top_editorial = max(editorial_scores, key=editorial_scores.get)
        editorial_conf = editorial_scores[top_editorial]
        source_votes.append((
            top_editorial,
            editorial_conf,
            SOURCE_WEIGHTS["editorial"],
            "编辑评价",
        ))

    if not source_votes:
        return {
            "consensus_emotion": "未知",
            "confidence": 0,
            "agreement_level": "无",
            "vote_detail": [],
            "weighted_score": {},
            "suggestions": ["暂无外部数据，建议先同步 Apple Music 或等待 B站/网易云数据"],
        }

    # 加权投票
    weighted: dict[str, float] = {}
    vote_detail: list[dict] = []

    for emotion, conf, weight, label in source_votes:
        weighted_score = conf * weight
        weighted[emotion] = weighted.get(emotion, 0) + weighted_score
        vote_detail.append({
            "source": label,
            "emotion": emotion,
            "confidence": round(conf, 3),
            "weight": weight,
            "weighted_score": round(weighted_score, 3),
        })

    # 共识情绪（加权最高分）
    if weighted:
        consensus_emotion = max(weighted, key=weighted.get)
        consensus_score = weighted[consensus_emotion]
    else:
        consensus_emotion = "未知"
        consensus_score = 0

    # 一致度评级
    # 分母用「实际参与投票的源权重和」而非全部源权重和：
    # 缺失的数据源（B站无结果、无编辑评价等）不应稀释一致度，
    # 否则数据源越少一致度越低，单源时永远达不到「高」。
    total_weight = sum(w for _, _, w, _ in source_votes)
    normalized_score = consensus_score / total_weight if total_weight > 0 else 0

    agreement = (
        "高" if normalized_score >= 0.5
        else "中" if normalized_score >= 0.25
        else "低" if normalized_score >= 0.1
        else "无"
    )

    # AI 与共识的差别
    ai_emotion = ai_prediction["emotion"] if ai_prediction else None
    ai_matches_consensus = ai_emotion == consensus_emotion

    suggestions: list[str] = []
    if ai_emotion and not ai_matches_consensus:
        if normalized_score >= 0.4:
            suggestions.append(
                f"多源共识「{consensus_emotion}」(得分{normalized_score:.0%})与AI预测「{ai_emotion}」存在显著分歧"
            )
        if normalized_score >= AUTO_CORRECT_THRESHOLD:
            suggestions.append(
                f"共识度{normalized_score:.0%}超过{AUTO_CORRECT_THRESHOLD:.0%}阈值，建议自动纠正"
            )
    elif ai_matches_consensus:
        suggestions.append(f"多源共识与AI预测一致「{consensus_emotion}」，置信度高")

    if len(source_votes) < 3:
        suggestions.append(f"数据源({len(source_votes)}个)偏少，建议扩充多平台反馈")

    return {
        "consensus_emotion": consensus_emotion,
        "confidence": round(normalized_score, 3),
        "agreement_level": agreement,
        "vote_detail": vote_detail,
        "weighted_score": {k: round(v, 3) for k, v in sorted(weighted.items(), key=lambda x: -x[1])},
        "ai_matches_consensus": ai_matches_consensus,
        "suggestions": suggestions,
    }


async def _auto_correct_if_needed(
    db: AsyncSession,
    song: Song,
    ai_prediction: dict | None,
    consensus: dict[str, Any],
) -> dict[str, Any] | None:
    """多源共识差异 > 阈值时，自动纠正情绪标签。

    触发条件：
    1. 加权共识置信度 ≥ AUTO_CORRECT_THRESHOLD (40%)
    2. 共识情绪 ≠ AI 预测情绪
    3. 一致度评级 ≠ "高"
    """
    if not ai_prediction or not consensus:
        return None

    consensus_emotion = consensus.get("consensus_emotion", "未知")
    consensus_confidence = consensus.get("confidence", 0)
    ai_emotion = ai_prediction["emotion"]
    ai_confidence = ai_prediction["confidence"]
    agreement = consensus.get("agreement_level", "无")

    # 条件检查
    if consensus_emotion == "未知" or consensus_emotion == ai_emotion:
        return {
            "corrected": False,
            "reason": f"共识({consensus_emotion})与AI({ai_emotion})一致，无需纠正",
        }

    if consensus_confidence < AUTO_CORRECT_THRESHOLD:
        return {
            "corrected": False,
            "reason": f"多源共识置信度{consensus_confidence:.0%}不足{AUTO_CORRECT_THRESHOLD:.0%}阈值",
        }

    if agreement == "高":
        return {"corrected": False, "reason": "一致度较高，跳过纠正"}

    confidence_gap = abs(consensus_confidence - ai_confidence)

    # 执行纠正
    logger.info(
        "自动纠正: #%d (%s - %s) AI「%s」→ 多源共识「%s」(gap=%.0f%%)",
        song.id, song.title, song.artist, ai_emotion, consensus_emotion, confidence_gap,
    )

    emo_result = await db.execute(
        select(Emotion).where(Emotion.name == consensus_emotion)
    )
    target_emotion = emo_result.scalar_one_or_none()

    if not target_emotion:
        return {"corrected": False, "reason": f"情绪模板中未找到「{consensus_emotion}」"}

    new_pred = AiPrediction(
        song_id=song.id,
        emotion_id=target_emotion.id,
        confidence=consensus_confidence,
        feature_vector=None,
        model_version="multi_source_corrected_v1",
    )
    db.add(new_pred)
    await db.commit()

    logger.info(
        "纠正完成: #%d → %s (%.0f%%)",
        song.id, consensus_emotion, consensus_confidence,
    )

    return {
        "corrected": True,
        "previous_emotion": ai_emotion,
        "previous_confidence": ai_confidence,
        "new_emotion": consensus_emotion,
        "new_confidence": consensus_confidence,
        "confidence_gap": round(confidence_gap, 3),
        "agreement_level": agreement,
        "source": "multi_source_consensus",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


async def batch_feedback(db: AsyncSession, limit: int = 20) -> dict[str, Any]:
    """批量采集多源外部反馈。"""
    result = await db.execute(
        select(Song).order_by(Song.id.desc()).limit(limit)
    )
    songs = result.scalars().all()

    total = len(songs)
    done = 0
    errors = 0

    for song in songs:
        try:
            await collect_external_feedback(db, song.id, force=True)
            done += 1
        except Exception:
            logger.exception("反馈采集失败: %s - %s", song.title, song.artist)
            errors += 1

    return {"total": total, "done": done, "errors": errors}