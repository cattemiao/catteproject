"""SQLAlchemy 异步引擎与 Session 管理。"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """所有模型的声明基类。"""


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供数据库会话。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """启动时自动建表（开发期使用，生产期建议用 Alembic 迁移）。"""
    # 导入所有模型以确保它们注册到 Base.metadata
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_lightweight_migrations)


def _apply_lightweight_migrations(sync_conn) -> None:
    """轻量迁移：为已存在的表补充新列（开发期 SQLite/Postgres 通用）。

    正式环境建议改用 Alembic。这里只处理新增列的场景。
    """
    from sqlalchemy import inspect, text

    from app.database import Base

    inspector = inspect(sync_conn)

    # 清理历史上迁移中断遗留的重建临时表（SQLite 索引名全局唯一，残留表会占用 ix_songs_* 名称）
    sync_conn.execute(text("DROP TABLE IF EXISTS _songs_old"))

    # songs: 新增 platform / netease_id / user_id；去掉 apple_music_id 的 unique 约束（重建表）
    if "songs" in inspector.get_table_names():
        song_cols = {c["name"] for c in inspector.get_columns("songs")}
        # SQLite 无法 ALTER 删除 unique 约束，重建表
        has_apple_unique = any(
            "apple_music_id" in uc["column_names"]
            for uc in inspector.get_unique_constraints("songs")
        )
        # 也检查 unique 索引（SQLite 列级 UNIQUE 在 index_list 里体现）
        if not has_apple_unique:
            for idx in inspector.get_indexes("songs"):
                if "apple_music_id" in idx.get("column_names", []) and idx.get("unique"):
                    has_apple_unique = True
                    break
        if has_apple_unique:
            # SQLite 索引名全局唯一：先删除旧索引，避免新表创建同名索引时冲突
            for idx in inspector.get_indexes("songs"):
                if idx.get("name"):
                    sync_conn.execute(text(f'DROP INDEX IF EXISTS "{idx["name"]}"'))
            sync_conn.execute(text("ALTER TABLE songs RENAME TO _songs_old"))
            Base.metadata.tables["songs"].create(sync_conn, checkfirst=True)
            old_cols = [c["name"] for c in inspect(sync_conn).get_columns("_songs_old")]
            common = [c for c in ["id", "apple_music_id", "platform", "netease_id", "title",
                                   "artist", "album", "duration_ms", "raw_meta", "type",
                                   "artist_bio"] if c in old_cols]
            # NOT NULL 列：已有列用 COALESCE 兜底 NULL，新表有而旧表没有的列用模型默认值填充
            insert_cols = list(common)
            select_cols = []
            for c in common:
                if c == "platform":
                    select_cols.append("COALESCE(platform, 'apple') AS platform")
                elif c == "type":
                    select_cols.append("COALESCE(type, 'song') AS type")
                else:
                    select_cols.append(c)
            for col, default in (("platform", "'apple'"), ("type", "'song'")):
                if col not in old_cols:
                    insert_cols.append(col)
                    select_cols.append(f"{default} AS {col}")
            col_list = ", ".join(insert_cols)
            sel_list = ", ".join(select_cols)
            sync_conn.execute(text(
                f"INSERT INTO songs ({col_list}) SELECT {sel_list} FROM _songs_old"
            ))
            sync_conn.execute(text("DROP TABLE _songs_old"))
        else:
            if "platform" not in song_cols:
                sync_conn.execute(
                    text("ALTER TABLE songs ADD COLUMN platform VARCHAR(16) DEFAULT 'apple' NOT NULL")
                )
            if "netease_id" not in song_cols:
                sync_conn.execute(text("ALTER TABLE songs ADD COLUMN netease_id VARCHAR(64)"))
            if "user_id" not in song_cols:
                sync_conn.execute(text("ALTER TABLE songs ADD COLUMN user_id INTEGER"))

    # users: 新增 netease_cookie / netease_uid / netease_profile
    if "users" in inspector.get_table_names():
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "netease_cookie" not in user_cols:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN netease_cookie VARCHAR(2048)"))
        if "netease_uid" not in user_cols:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN netease_uid VARCHAR(64)"))
        if "netease_profile" not in user_cols:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN netease_profile JSON"))

    # 补建 models 定义的缺失索引（SQLite 的 create_all 不会为已存在表补建索引）
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.tables.values():
        if table.name not in existing_tables:
            continue
        for idx in table.indexes:
            idx.create(sync_conn, checkfirst=True)
