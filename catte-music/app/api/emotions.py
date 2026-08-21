"""情绪路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.prediction import AiPrediction
from app.models.song import Song, SongEmotion
from app.models.user import Emotion, EmotionDimension
from app.schemas.emotion import EmotionOut, PredictionOut, RadarDimension, RadarOut
from app.services.ai.model import EMOTION_COLORS, FUZZY_THRESHOLD

router = APIRouter(prefix="/api", tags=["情绪"])


@router.get("/emotions", response_model=list[EmotionOut])
async def list_emotions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Emotion))
    return [EmotionOut.model_validate(e) for e in result.scalars().all()]


@router.get("/songs/{song_id}/emotion", response_model=PredictionOut)
async def get_song_emotion(song_id: int, db: AsyncSession = Depends(get_db)):
    """返回最近一次 AI 预测的情绪。"""
    result = await db.execute(
        select(AiPrediction)
        .where(AiPrediction.song_id == song_id)
        .options(joinedload(AiPrediction.emotion_rel))
        .order_by(AiPrediction.id.desc())
        .limit(1)
    )
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="该歌曲暂无情绪分析数据")

    # 旧数据（v1 单标签）emotion_probs 为 NULL → 多标签字段返回 None，前端降级
    probs = pred.emotion_probs
    top_emotions = None
    fuzzy = None
    if probs:
        ranked = sorted(probs.items(), key=lambda x: -x[1])[:5]
        top_emotions = [
            {
                "name": name,
                "color": pred.emotion_rel.color if name == pred.emotion_rel.name else EMOTION_COLORS.get(name, "#a855f7"),
                "prob": round(float(prob), 4),
            }
            for name, prob in ranked
        ]
        fuzzy = float(probs.get(pred.emotion_rel.name, 0.0)) < FUZZY_THRESHOLD

    return PredictionOut(
        song_id=song_id,
        emotion=pred.emotion_rel.name,
        color=pred.emotion_rel.color,
        confidence=pred.confidence,
        top_emotions=top_emotions,
        probs=probs,
        fuzzy=fuzzy,
        model_version=pred.model_version,
    )


@router.get("/songs/{song_id}/radar", response_model=RadarOut)
async def get_song_radar(song_id: int, db: AsyncSession = Depends(get_db)):
    """返回情绪雷达图 7 维数据 + 颜色。

    维度优先级：预测记录中保存的该歌曲真实音频特征 > 情绪模板维度；
    无任何分析数据时返回 404，由前端引导用户先进行分析。
    """
    result = await db.execute(
        select(AiPrediction)
        .where(AiPrediction.song_id == song_id)
        .options(joinedload(AiPrediction.emotion_rel).joinedload(Emotion.dimensions))
        .order_by(AiPrediction.id.desc())
        .limit(1)
    )
    pred = result.scalar_one_or_none()
    song_result = await db.execute(select(Song).where(Song.id == song_id))
    song = song_result.scalar_one_or_none()

    if not pred:
        raise HTTPException(status_code=404, detail="该歌曲暂无情绪分析数据")

    # 主情绪的标准模板维度（该情绪的一套典型画像），供前端与实测维度叠加对比
    template = None
    if pred.emotion_rel and pred.emotion_rel.dimensions:
        d = pred.emotion_rel.dimensions
        template = RadarDimension(
            loudness=d.loudness,
            high_freq=d.high_freq,
            rhythm=d.rhythm,
            soundstage=d.soundstage,
            layering=d.layering,
            soothing=d.soothing,
            prosody=d.prosody,
        )

    # 优先使用该歌曲真实测量的 7 维特征
    real = RadarDimension(
        loudness=pred.loudness, high_freq=pred.high_freq, rhythm=pred.rhythm,
        soundstage=pred.soundstage, layering=pred.layering,
        soothing=pred.soothing, prosody=pred.prosody,
    )
    has_real = any(v is not None for v in (
        real.loudness, real.high_freq, real.rhythm, real.soundstage,
        real.layering, real.soothing, real.prosody,
    ))
    if has_real:
        return RadarOut(
            song_id=song_id,
            title=song.title if song else "未知",
            emotion=pred.emotion_rel.name if pred.emotion_rel else "未知",
            color=pred.emotion_rel.color if pred.emotion_rel else "#a855f7",
            dimensions=real,
            template=template,
        )

    # 回退：情绪模板维度（每个情绪一套固定画像）
    if template:
        return RadarOut(
            song_id=song_id,
            title=song.title if song else "未知",
            emotion=pred.emotion_rel.name if pred.emotion_rel else "未知",
            color=pred.emotion_rel.color if pred.emotion_rel else "#a855f7",
            dimensions=template,
        )

    raise HTTPException(status_code=404, detail="该歌曲暂无情绪分析数据")