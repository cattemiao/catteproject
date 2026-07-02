"""情绪路由：查询情绪、雷达图数据、触发 AI 分析。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import AiPrediction
from app.models.song import Song, SongEmotion
from app.models.user import Emotion, EmotionDimension
from app.schemas.emotion import EmotionOut, PredictionOut, RadarDimension, RadarOut

router = APIRouter(prefix="/api", tags=["情绪"])


@router.get("/emotions", response_model=list[EmotionOut])
async def list_emotions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Emotion).order_by(Emotion.id))
    return [EmotionOut.model_validate(e) for e in result.scalars().all()]


@router.get("/songs/{song_id}/emotion", response_model=PredictionOut)
async def get_song_emotion(song_id: int, db: AsyncSession = Depends(get_db)):
    """获取歌曲的情绪预测结果。"""
    pred = await db.execute(
        select(AiPrediction, Emotion.name, Emotion.color)
        .join(Emotion, Emotion.id == AiPrediction.emotion_id)
        .where(AiPrediction.song_id == song_id)
        .order_by(AiPrediction.predicted_at.desc())
        .limit(1)
    )
    row = pred.first()
    if not row:
        raise HTTPException(status_code=404, detail="该歌曲暂无情绪分析结果")
    _, emotion_name, color = row
    return PredictionOut(
        song_id=song_id,
        emotion=emotion_name,
        color=color,
        confidence=row[0].confidence,
    )


@router.get("/songs/{song_id}/radar", response_model=RadarOut)
async def get_song_radar(song_id: int, db: AsyncSession = Depends(get_db)):
    """获取歌曲 7 维情绪雷达图数据。"""
    # 查歌曲 + 情绪 + 维度
    result = await db.execute(
        select(Song, Emotion.name, Emotion.color, EmotionDimension)
        .join(SongEmotion, SongEmotion.song_id == Song.id)
        .join(Emotion, Emotion.id == SongEmotion.emotion_id)
        .join(EmotionDimension, EmotionDimension.emotion_id == Emotion.id)
        .where(Song.id == song_id)
        .limit(1)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="该歌曲暂无雷达图数据")

    song, emotion_name, color, dim = row
    return RadarOut(
        song_id=song.id,
        title=song.title,
        emotion=emotion_name,
        color=color,
        dimensions=RadarDimension(
            loudness=dim.loudness,
            high_freq=dim.high_freq,
            vocal=dim.vocal,
            rhythm=dim.rhythm,
            soundstage=dim.soundstage,
            space=dim.space,
            layering=dim.layering,
        ),
    )
