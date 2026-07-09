"""用户、情绪、收藏相关模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    apple_music_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    favorites: Mapped[list["UserFavorite"]] = relationship(back_populates="user")


class Emotion(Base):
    __tablename__ = "emotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    color: Mapped[str] = mapped_column(String(16))  # 主色调 hex

    dimensions: Mapped["EmotionDimension"] = relationship(back_populates="emotion")


class EmotionDimension(Base):
    """情绪的 7 维可视化数据（响度、高频、节奏、声场、层次、舒缓、韵律）。"""

    __tablename__ = "emotion_dimensions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emotion_id: Mapped[int] = mapped_column(ForeignKey("emotions.id"), index=True)
    loudness: Mapped[float] = mapped_column(default=0.0)
    high_freq: Mapped[float] = mapped_column(default=0.0)
    rhythm: Mapped[float] = mapped_column(default=0.0)
    soundstage: Mapped[float] = mapped_column(default=0.0)
    layering: Mapped[float] = mapped_column(default=0.0)
    soothing: Mapped[float] = mapped_column(default=0.0)
    prosody: Mapped[float] = mapped_column(default=0.0)

    emotion: Mapped[Emotion] = relationship(back_populates="dimensions")


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), primary_key=True)

    user: Mapped[User] = relationship(back_populates="favorites")
