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
        return PredictionOut(song_id=song_id, emotion="未知", color="#a855f7", confidence=0.0)
    return PredictionOut(
        song_id=song_id,
        emotion=pred.emotion_rel.name,
        color=pred.emotion_rel.color,
        confidence=pred.confidence,
    )


@router.get("/songs/{song_id}/radar", response_model=RadarOut)
async def get_song_radar(song_id: int, db: AsyncSession = Depends(get_db)):
    """返回情绪雷达图 7 维数据 + 颜色。"""
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

    if not pred or not pred.emotion_rel or not pred.emotion_rel.dimensions:
        # 没有维度数据 → 返回默认中性值
        return RadarOut(
            song_id=song_id,
            title=song.title if song else "未知",
            emotion="未知",
            color="#a855f7",
            dimensions=RadarDimension(
                loudness=50, high_freq=50, rhythm=50,
                soundstage=50, layering=50, soothing=50, prosody=50,
            ),
        )

    dim = pred.emotion_rel.dimensions
    return RadarOut(
        song_id=song_id,
        title=song.title if song else "未知",
        emotion=pred.emotion_rel.name,
        color=pred.emotion_rel.color,
        dimensions=RadarDimension(
            loudness=dim.loudness,
            high_freq=dim.high_freq,
            rhythm=dim.rhythm,
            soundstage=dim.soundstage,
            layering=dim.layering,
            soothing=dim.soothing,
            prosody=dim.prosody,
        ),
    )