"""歌曲相关 Pydantic 模型。"""
from pydantic import BaseModel


class SongOut(BaseModel):
    id: int
    apple_music_id: str
    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None

    model_config = {"from_attributes": True}


class SongListOut(BaseModel):
    total: int
    items: list[SongOut]


class FavoriteOut(BaseModel):
    song_id: int
    favorited: bool
