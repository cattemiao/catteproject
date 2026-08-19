"""歌曲相关 Pydantic 模型。"""
from pydantic import BaseModel


class SongOut(BaseModel):
    id: int
    apple_music_id: str
    platform: str = "apple"  # apple/netease
    netease_id: str | None = None
    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    preview_url: str | None = None
    raw_meta: dict | None = None
    type: str = "song"
    artist_bio: str | None = None
    artwork_url: str | None = None
    user_id: int | None = None  # 歌曲归属（用于判断是否可分享）

    model_config = {"from_attributes": True}


class SongListOut(BaseModel):
    total: int
    items: list[SongOut]
