"""系统设置服务：自动分析阈值、admin 密码等 key-value 配置的读写。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.setting import Setting
from app.utils.security import hash_password, verify_password

KEY_AUTO_ANALYZE_THRESHOLD = "auto_analyze_threshold"
KEY_ADMIN_PASSWORD_HASH = "admin_password_hash"

# 默认活跃用户阈值：低于该值时后台自动触发 AI 分析
DEFAULT_AUTO_ANALYZE_THRESHOLD = 5


async def get_setting_value(
    db: AsyncSession, key: str, default: str | None = None
) -> str | None:
    """读取一条设置；不存在或值为空时返回 default。"""
    row = (
        await db.execute(select(Setting).where(Setting.key == key))
    ).scalar_one_or_none()
    return (row.value if row and row.value else default)


async def set_setting_value(db: AsyncSession, key: str, value: str) -> None:
    """写入一条设置（upsert）。"""
    row = (
        await db.execute(select(Setting).where(Setting.key == key))
    ).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


async def get_auto_analyze_threshold(db: AsyncSession) -> int:
    """读取自动 AI 分析触发的活跃用户阈值。"""
    raw = await get_setting_value(
        db, KEY_AUTO_ANALYZE_THRESHOLD, str(DEFAULT_AUTO_ANALYZE_THRESHOLD)
    )
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_AUTO_ANALYZE_THRESHOLD


async def get_admin_password_hash(db: AsyncSession) -> str | None:
    """读取 admin 密码哈希（设置页修改后持久化；未修改过则返回 None）。"""
    return await get_setting_value(db, KEY_ADMIN_PASSWORD_HASH)


async def set_admin_password(db: AsyncSession, new_password: str) -> None:
    """保存 admin 新密码（bcrypt 哈希）。"""
    await set_setting_value(db, KEY_ADMIN_PASSWORD_HASH, hash_password(new_password))


async def verify_admin_password(db: AsyncSession, plain: str) -> bool:
    """校验 admin 密码：优先数据库哈希（设置页修改后的密码），否则 .env 明文。"""
    stored = await get_admin_password_hash(db)
    if stored:
        return verify_password(plain, stored)
    return bool(settings.admin_password) and plain == settings.admin_password
