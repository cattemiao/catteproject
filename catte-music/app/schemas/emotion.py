"""情绪相关 Pydantic 模型。"""
from pydantic import BaseModel


class EmotionOut(BaseModel):
    id: int
    name: str
    color: str

    model_config = {"from_attributes": True}


class RadarDimension(BaseModel):
    loudness: float
    high_freq: float
    vocal: float
    rhythm: float
    soundstage: float
    space: float
    layering: float


class RadarOut(BaseModel):
    song_id: int
    title: str
    emotion: str
    color: str
    dimensions: RadarDimension


class PredictionOut(BaseModel):
    song_id: int
    emotion: str
    color: str
    confidence: float
