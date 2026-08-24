"""后台自动 AI 分析任务。

当系统负载较低（当前活跃用户数低于阈值）时，
周期性地扫描尚未进行 AI 分析的专辑/歌单，逐个触发分析以生成情绪数据。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analyze import analyze_song_core
from app.database import async_session_factory
from app.models.prediction import AiPrediction
from app.models.song import CrawlRecord, Song
from app.services.active_users import active_users
from app.services.admin_settings import get_auto_analyze_threshold

logger = logging.getLogger(__name__)

# 每个轮询周期最多分析的数量（避免占用过多带宽/CPU）
BATCH_SIZE = 2
# 两次分析之间的间隔（秒），对网易云/Apple 接口限速
INTER_ANALYZE_DELAY = 8.0
# 轮询间隔（秒）：多久检查一次负载与待分析队列
POLL_INTERVAL = 60.0
# 分析失败的专辑/歌单在多长时间内不再重试
RETRY_COOLDOWN = timedelta(hours=24)

# 自动分析尝试记录标识（写入 crawl_records 表）
ATTEMPT_SOURCE = "auto_analyze"

# 防止 uvicorn --reload 等场景下重复启动循环
_running = False


async def _fetch_pending(session: AsyncSession, limit: int = BATCH_SIZE) -> list[Song]:
    """取尚未分析的专辑/歌单。

    条件：在 ai_predictions 中无任何记录，且近期（冷却期内）没有被自动分析尝试过。
    """
    cutoff = datetime.now() - RETRY_COOLDOWN
    attempted = (
        select(CrawlRecord.target_id)
        .where(
            CrawlRecord.source == ATTEMPT_SOURCE,
            CrawlRecord.crawled_at >= cutoff,
        )
        .distinct()
    )
    return list(
        (
            await session.execute(
                select(Song)
                .outerjoin(AiPrediction, AiPrediction.song_id == Song.id)
                .where(
                    Song.type.in_(("albums", "playlists")),
                    AiPrediction.id.is_(None),
                    Song.id.not_in(attempted),
                )
                .order_by(Song.id)
                .limit(limit)
            )
        ).scalars().all()
    )


async def _record_attempt(session: AsyncSession, song_id: int, status: str) -> None:
    """记录一次自动分析尝试（success/failed）。"""
    session.add(
        CrawlRecord(
            source=ATTEMPT_SOURCE,
            target_id=str(song_id),
            status=status,
            crawled_at=datetime.now(),
        )
    )


async def run_auto_analyze_cycle() -> dict:
    """执行一轮自动分析：负载检查 → 扫描待分析 → 逐个分析。

    Returns:
        {"active_users", "threshold", "analyzed", "skipped"}
    """
    async with async_session_factory() as db:
        threshold = await get_auto_analyze_threshold(db)

    active = active_users.active_count()
    if active >= threshold:
        logger.info("活跃用户数 %d >= 阈值 %d，本轮跳过自动分析", active, threshold)
        return {"active_users": active, "threshold": threshold, "analyzed": 0, "skipped": True}

    async with async_session_factory() as db:
        pending_ids = [s.id for s in await _fetch_pending(db)]

    analyzed = 0
    for song_id in pending_ids:
        # 每个专辑使用独立会话，避免失败后 rollback 使其他对象过期
        async with async_session_factory() as db:
            song = await db.get(Song, song_id)
            if song is None:
                continue
            song_title = song.title
            try:
                # cookies=None：后台无用户登录态，网易云试听回退外链播放器
                await analyze_song_core(song, db, cookies=None)
                await _record_attempt(db, song_id, "success")
                await db.commit()
                analyzed += 1
            except Exception as exc:
                await db.rollback()
                await _record_attempt(db, song_id, "failed")
                await db.commit()
                logger.warning("自动分析专辑 #%d (%s) 失败: %s", song_id, song_title, exc)
        await asyncio.sleep(INTER_ANALYZE_DELAY)

    logger.info(
        "自动 AI 分析完成: 处理 %d 张专辑/歌单（活跃用户 %d/%d）",
        analyzed, active, threshold,
    )
    return {"active_users": active, "threshold": threshold, "analyzed": analyzed, "skipped": False}


async def auto_analyze_loop() -> None:
    """常驻循环：应用启动后由 lifespan 创建，定期执行分析周期。"""
    global _running
    if _running:
        logger.warning("自动 AI 分析循环已在运行，跳过重复启动")
        return
    _running = True
    try:
        while True:
            try:
                await run_auto_analyze_cycle()
            except Exception:
                logger.exception("自动 AI 分析周期执行异常")
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        _running = False
