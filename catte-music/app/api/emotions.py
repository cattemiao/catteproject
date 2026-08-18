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
        raise HTTPException(status_code=404, detail="该歌曲暂无情绪分析数据")
    return PredictionOut(
        song_id=song_id,
        emotion=pred.emotion_rel.name,
        color=pred.emotion_rel.color,
        confidence=pred.confidence,
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
        )

    # 回退：情绪模板维度（每个情绪一套固定画像）
    if pred.emotion_rel and pred.emotion_rel.dimensions:
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

    raise HTTPException(status_code=404, detail="该歌曲暂无情绪分析数据")