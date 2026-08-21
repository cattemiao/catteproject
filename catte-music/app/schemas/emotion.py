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
    rhythm: float
    soundstage: float
    layering: float
    soothing: float
    prosody: float


class RadarOut(BaseModel):
    song_id: int
    title: str
    emotion: str
    color: str
    dimensions: RadarDimension
    # 主情绪的标准模板维度画像，用于与歌曲实测维度叠加对比
    template: RadarDimension | None = None


class EmotionProbOut(BaseModel):
    name: str
    color: str
    prob: float


class PredictionOut(BaseModel):
    song_id: int
    emotion: str
    color: str
    confidence: float
    # v2 多标签字段（旧数据为 None，前端降级单标签展示）
    top_emotions: list[EmotionProbOut] | None = None
    probs: dict[str, float] | None = None
    fuzzy: bool | None = None
    model_version: str | None = None