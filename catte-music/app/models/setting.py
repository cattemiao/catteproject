"""系统设置模型（key-value 存储）。

存放需要在运行期修改、并持久化的配置项，例如：
- auto_analyze_threshold：自动 AI 分析触发的活跃用户数阈值
- admin_password_hash：admin 账号在设置页修改后的密码哈希（初始密码来自 .env）
"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
