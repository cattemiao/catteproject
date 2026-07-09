"""歌曲、标签、爬虫记录相关模型。"""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

# 兼容 SQLite（开发期不支持 JSONB）与 PostgreSQL
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Song(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    apple_music_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    artist: Mapped[str] = mapped_column(String(256))
    album: Mapped[str | None] = mapped_column(String(256), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    raw_meta: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    type: Mapped[str] = mapped_column(String(16), default="song")  # song/album
    artist_bio: Mapped[str | None] = mapped_column(String(512), nullable=True)

    emotions: Mapped[list["SongEmotion"]] = relationship(back_populates="song")
    tags: Mapped[list["SongTag"]] = relationship(back_populates="song")
    predictions: Mapped[list["AiPrediction"]] = relationship(back_populates="song")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class SongTag(Base):
    __tablename__ = "song_tags"

    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="crawler")  # crawler/user/ai

    song: Mapped[Song] = relationship(back_populates="tags")


class SongEmotion(Base):
    __tablename__ = "song_emotions"

    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), primary_key=True)
    emotion_id: Mapped[int] = mapped_column(ForeignKey("emotions.id"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    song: Mapped[Song] = relationship(back_populates="emotions")


class CrawlRecord(Base):
    __tablename__ = "crawl_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="success")
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
