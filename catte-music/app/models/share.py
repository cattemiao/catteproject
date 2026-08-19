"""用户分享与点赞模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Share(Base):
    """用户分享：AI 分析完成后可将专辑/播放列表分享到社区推荐列表。"""

    __tablename__ = "shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True)
    # 分享来源平台，从 songs.platform 冗余（apple/netease），推荐时按平台过滤
    platform: Mapped[str] = mapped_column(String(16), index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)  # 分享语（可选）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User")
    song: Mapped["Song"] = relationship("Song")
    likes: Mapped[list["Like"]] = relationship(back_populates="share")


class Like(Base):
    """点赞：同一用户对同一分享只能点一次（UNIQUE 约束）。"""

    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("user_id", "share_id", name="uq_like_user_share"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[int] = mapped_column(ForeignKey("shares.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    share: Mapped[Share] = relationship(back_populates="likes")
