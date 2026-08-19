"""分享与点赞相关 Pydantic 模型。"""
from datetime import datetime

from pydantic import BaseModel

from app.schemas.song import SongOut


class ShareCreate(BaseModel):
    song_id: int
    comment: str | None = None


class ShareOut(BaseModel):
    id: int
    song: SongOut
    sharer_id: int
    sharer_username: str
    platform: str
    comment: str | None = None
    like_count: int = 0
    user_liked: bool = False
    created_at: datetime
    # 分享歌曲的 AI 情绪名（最新预测），用于卡片徽章
    emotion: str | None = None
    # 与当前用户情绪画像的相似度（推荐时计算），随机兜底项为 None
    similarity: float | None = None

    model_config = {"from_attributes": True}


class LikeOut(BaseModel):
    share_id: int
    liked: bool
    like_count: int


class ShareStatus(BaseModel):
    shared: bool
    share_id: int | None = None
