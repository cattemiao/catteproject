"""AI 预测结果模型。"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class AiPrediction(Base):
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True)
    emotion_id: Mapped[int] = mapped_column(ForeignKey("emotions.id"))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    feature_vector: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), default="v0.1")
    # 该歌曲真实音频特征映射的 7 维情绪指标（分析时写入，雷达图使用）
    loudness: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_freq: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhythm: Mapped[float | None] = mapped_column(Float, nullable=True)
    soundstage: Mapped[float | None] = mapped_column(Float, nullable=True)
    layering: Mapped[float | None] = mapped_column(Float, nullable=True)
    soothing: Mapped[float | None] = mapped_column(Float, nullable=True)
    prosody: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    song: Mapped["Song"] = relationship(back_populates="predictions")  # noqa: F821
    emotion_rel: Mapped["Emotion"] = relationship("Emotion")  # noqa: F821
