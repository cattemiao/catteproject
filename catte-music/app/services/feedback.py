"""外部数据反馈与模型持续优化模块。

从 B 站等平台采集音乐风格数据，与 AI 情绪预测对比，
共识差异 > 40% 时自动纠正情绪标签。
"""
from __future__ import annotations

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
)
from app.services.enrich import analyze_editorial_sentiment

logger = logging.getLogger(__name__)

# 自动纠正阈值：外部共识置信度差超过此值则自动覆盖 AI 预测
AUTO_CORRECT_THRESHOLD = 0.4


async def collect_external_feedback(
    db: AsyncSession,
    song_id: int,
    force: bool = False,
) -> dict[str, Any]:
    """为单首歌曲采集外部平台风格反馈数据。

    返回多源数据对比结果，供前端展示与模型调优。
    """
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        return {"error": "歌曲不存在"}

    title = song.title
    artist = song.artist

    # 1. B 站风格标签
    bili_styles = await get_song_external_styles(title, artist)

    # 2. B 站评论情绪
    bili_emotions = await get_song_comment_emotions(title, artist)

    # 3. Apple Music 编辑评论情感
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

    # 4. AI 预测
    pred_result = await db.execute(
        select(AiPrediction)
        .where(AiPrediction.song_id == song.id)
        .order_by(AiPrediction.id.desc())
        .limit(1)
    )
    pred = pred_result.scalar_one_or_none()

    ai_prediction = None
    if pred:
        from sqlalchemy.orm import joinedload
        pred_with_rel = await db.execute(
            select(AiPrediction)
            .where(AiPrediction.id == pred.id)
            .options(joinedload(AiPrediction.emotion_rel))
            .limit(1)
        )
        pred = pred_with_rel.scalar_one_or_none()
        if pred and pred.emotion_rel:
            ai_prediction = {
                "emotion": pred.emotion_rel.name,
                "confidence": pred.confidence,
            }

    # 5. 多源对比
    comparison = _cross_validate(
        ai_prediction=ai_prediction,
        bili_primary=bili_styles.get("primary_style"),
        bili_confidence=bili_styles.get("confidence", 0),
        bili_emotions=bili_emotions,
        editorial_scores=editorial_scores,
    )

    # 6. 自动纠正：共识差异 > 40% 时以外部公认结果覆盖 AI 预测
    correction = await _auto_correct_if_needed(
        db=db,
        song=song,
        ai_prediction=ai_prediction,
        comparison=comparison,
        bili_primary=bili_styles.get("primary_style"),
        bili_confidence=bili_styles.get("confidence", 0),
    )

    # 7. 存储反馈结果到 raw_meta
    feedback = {
        "bilibili_styles": bili_styles,
        "bilibili_emotions": bili_emotions,
        "editorial_scores": editorial_scores,
        "ai_prediction": ai_prediction,
        "cross_validation": comparison,
        "auto_correction": correction,
        "updated_at": datetime.datetime.utcnow().isoformat(),
    }

    if song.raw_meta is None:
        song.raw_meta = {}
    song.raw_meta["_external_feedback"] = feedback
    await db.commit()

    return feedback


def _cross_validate(
    ai_prediction: dict | None,
    bili_primary: str | None,
    bili_confidence: float,
    bili_emotions: dict[str, float],
    editorial_scores: dict[str, float],
) -> dict[str, Any]:
    """多源数据交叉验证，判断 AI 预测一致性与建议调整方向。"""
    sources: dict[str, str] = {}
    sources["ai"] = ai_prediction["emotion"] if ai_prediction else "未知"

    sources["bilibili"] = bili_primary or "无数据"

    top_editorial = max(editorial_scores, key=editorial_scores.get) if editorial_scores else None
    sources["editorial"] = top_editorial or "无数据"

    # 计算一致性
    votes: dict[str, int] = {}
    if ai_prediction:
        votes[ai_prediction["emotion"]] = votes.get(ai_prediction["emotion"], 0) + 1
    if bili_primary:
        votes[bili_primary] = votes.get(bili_primary, 0) + 1
    if top_editorial:
        votes[top_editorial] = votes.get(top_editorial, 0) + 1

    max_votes = max(votes.values()) if votes else 0
    consensus_emotion = max(votes, key=votes.get) if votes else "未知"

    agreement = (
        "高" if max_votes >= 3
        else "中" if max_votes == 2
        else "低" if max_votes >= 1
        else "无"
    )

    # 模型调优建议
    suggestions: list[str] = []
    if ai_prediction and bili_primary:
        if ai_prediction["emotion"] != bili_primary and bili_confidence > 0.3:
            suggestions.append(
                f"B站标签指向「{bili_primary}」(置信度{bili_confidence:.0%})，"
                f"与AI预测「{ai_prediction['emotion']}」不一致，建议复核模板参数"
            )
        elif ai_prediction["emotion"] == bili_primary:
            suggestions.append(
                f"B站标签与AI预测一致「{bili_primary}」，置信度高"
            )

    if top_editorial and ai_prediction and top_editorial != ai_prediction["emotion"]:
        suggestions.append(
            f"编辑评论暗示「{top_editorial}」，建议检查特征向量的情绪映射"
        )

    if not suggestions:
        suggestions.append("多源数据量不足，建议扩充外部反馈数据")

    return {
        "sources": sources,
        "consensus_emotion": consensus_emotion,
        "agreement_level": agreement,
        "vote_counts": votes,
        "suggestions": suggestions,
        "bili_confidence": bili_confidence,
    }


async def _auto_correct_if_needed(
    db: AsyncSession,
    song: Song,
    ai_prediction: dict | None,
    comparison: dict[str, Any],
    bili_primary: str | None,
    bili_confidence: float,
) -> dict[str, Any] | None:
    """共识差异 > 阈值时，自动将歌曲情绪纠正为外部公认结果。

    条件：
    1. B 站风格标签置信度 ≥ AUTO_CORRECT_THRESHOLD (40%)
    2. B 站标签 与 AI 预测不一致
    3. 一致度评级为「低」或「中」

    纠正动作：
    - 创建新 AiPrediction，标记 source="auto_corrected"
    - 置信度设为 bili_confidence
    """
    if not ai_prediction or not bili_primary:
        return None

    ai_emotion = ai_prediction["emotion"]
    ai_confidence = ai_prediction["confidence"]

    # 条件 1：B 站置信度足够高
    if bili_confidence < AUTO_CORRECT_THRESHOLD:
        return {"corrected": False, "reason": f"B站置信度{bili_confidence:.0%}不足{AUTO_CORRECT_THRESHOLD:.0%}阈值"}

    # 条件 2：情绪不一致
    if bili_primary == ai_emotion:
        return {"corrected": False, "reason": f"B站({bili_primary})与AI({ai_emotion})一致，无需纠正"}

    # 条件 3：共识差距够大
    confidence_gap = abs(bili_confidence - ai_confidence)
    agreement = comparison.get("agreement_level", "无")
    if agreement == "高":
        return {"corrected": False, "reason": "多源一致度较高，跳过自动纠正"}

    # 确认是否需要纠正（差 > 40% 或一致度低）
    if confidence_gap < AUTO_CORRECT_THRESHOLD and agreement == "中":
        return {"corrected": False, "reason": f"置信度差{confidence_gap:.0%}未达阈值，一致度中等暂不纠正"}

    # ── 执行纠正 ──
    logger.info(
        "自动纠正: 歌曲 #%d (%s - %s) AI预测「%s」→ B站公认「%s」(gap=%.0f%%)",
        song.id, song.title, song.artist, ai_emotion, bili_primary, confidence_gap,
    )

    # 查找目标情绪
    from sqlalchemy import select as _select
    emo_result = await db.execute(
        _select(Emotion).where(Emotion.name == bili_primary)
    )
    target_emotion = emo_result.scalar_one_or_none()

    if not target_emotion:
        return {"corrected": False, "reason": f"情绪模板中未找到「{bili_primary}」"}

    # 写入新的 AiPrediction（标记为自动纠正）
    new_pred = AiPrediction(
        song_id=song.id,
        emotion_id=target_emotion.id,
        confidence=bili_confidence,
        feature_vector=None,
        model_version="auto_corrected_v1",
    )
    db.add(new_pred)
    await db.commit()

    logger.info(
        "自动纠正完成: 歌曲 #%d → %s (置信度 %.0f%%)",
        song.id, bili_primary, bili_confidence,
    )

    return {
        "corrected": True,
        "previous_emotion": ai_emotion,
        "previous_confidence": ai_confidence,
        "new_emotion": bili_primary,
        "new_confidence": bili_confidence,
        "confidence_gap": round(confidence_gap, 3),
        "agreement_level": agreement,
        "source": "bilibili_consensus",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


async def batch_feedback(db: AsyncSession, limit: int = 20) -> dict[str, Any]:
    """批量采集外部反馈数据。"""
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