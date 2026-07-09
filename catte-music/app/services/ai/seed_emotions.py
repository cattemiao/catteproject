"""初始化 20 种情绪标签 + 7 维模板到数据库。

维度：loudness, high_freq, rhythm, soundstage, layering, soothing, prosody
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import Emotion, EmotionDimension

logger = logging.getLogger(__name__)

# 20 种情绪模板（刻意拉开维度差异）
EMOTION_PROFILES: list[tuple[str, str, dict[str, float]]] = [
    # 名称, 颜色, {loudness, high_freq, rhythm, soundstage, layering, soothing, prosody}
    ("甜蜜",    "#ec4899", {"loudness": 55, "high_freq": 70, "rhythm": 60,  "soundstage": 45, "layering": 40, "soothing": 65, "prosody": 50}),
    ("浪漫",    "#f472b6", {"loudness": 50, "high_freq": 65, "rhythm": 55,  "soundstage": 60, "layering": 50, "soothing": 70, "prosody": 55}),
    ("治愈",    "#22d3ee", {"loudness": 45, "high_freq": 60, "rhythm": 50,  "soundstage": 55, "layering": 45, "soothing": 85, "prosody": 40}),
    ("悲伤",    "#3b82f6", {"loudness": 35, "high_freq": 30, "rhythm": 25,  "soundstage": 45, "layering": 25, "soothing": 35, "prosody": 30}),
    ("孤独",    "#64748b", {"loudness": 30, "high_freq": 35, "rhythm": 30,  "soundstage": 40, "layering": 20, "soothing": 30, "prosody": 25}),
    ("深情",    "#a855f7", {"loudness": 55, "high_freq": 50, "rhythm": 45,  "soundstage": 55, "layering": 55, "soothing": 60, "prosody": 50}),
    ("欢快",    "#fbbf24", {"loudness": 75, "high_freq": 80, "rhythm": 85,  "soundstage": 60, "layering": 60, "soothing": 50, "prosody": 75}),
    ("愤怒",    "#ef4444", {"loudness": 90, "high_freq": 85, "rhythm": 75,  "soundstage": 70, "layering": 80, "soothing": 5,  "prosody": 40}),
    ("宁静",    "#14b8a6", {"loudness": 20, "high_freq": 30, "rhythm": 15,  "soundstage": 50, "layering": 15, "soothing": 95, "prosody": 20}),
    ("热血",    "#f97316", {"loudness": 85, "high_freq": 70, "rhythm": 90,  "soundstage": 75, "layering": 80, "soothing": 15, "prosody": 60}),
    ("忧郁",    "#818cf8", {"loudness": 40, "high_freq": 40, "rhythm": 35,  "soundstage": 45, "layering": 30, "soothing": 40, "prosody": 35}),
    ("激昂",    "#f43f5e", {"loudness": 80, "high_freq": 65, "rhythm": 80,  "soundstage": 70, "layering": 75, "soothing": 20, "prosody": 70}),
    ("松弛",    "#34d399", {"loudness": 40, "high_freq": 45, "rhythm": 40,  "soundstage": 50, "layering": 35, "soothing": 75, "prosody": 30}),
    ("梦幻",    "#c084fc", {"loudness": 50, "high_freq": 75, "rhythm": 45,  "soundstage": 65, "layering": 60, "soothing": 60, "prosody": 45}),
    ("震撼",    "#e879f9", {"loudness": 95, "high_freq": 80, "rhythm": 70,  "soundstage": 85, "layering": 85, "soothing": 10, "prosody": 50}),
    ("舒缓",    "#10b981", {"loudness": 25, "high_freq": 35, "rhythm": 20,  "soundstage": 45, "layering": 25, "soothing": 92, "prosody": 22}),
    ("自由",    "#06b6d4", {"loudness": 60, "high_freq": 65, "rhythm": 65,  "soundstage": 55, "layering": 50, "soothing": 55, "prosody": 65}),
    ("空灵",    "#f0abfc", {"loudness": 30, "high_freq": 72, "rhythm": 25,  "soundstage": 70, "layering": 55, "soothing": 80, "prosody": 28}),
    ("狂野",    "#f59e0b", {"loudness": 88, "high_freq": 82, "rhythm": 88,  "soundstage": 78, "layering": 82, "soothing": 8,  "prosody": 68}),
    ("迷幻",    "#d946ef", {"loudness": 55, "high_freq": 78, "rhythm": 50,  "soundstage": 68, "layering": 72, "soothing": 45, "prosody": 42}),
]


async def seed() -> None:
    async with async_session_factory() as session:
        existing = (await session.execute(select(Emotion))).scalars().all()
        if existing:
            logger.info("情绪表已有 %d 条数据，跳过初始化", len(existing))
            return

        for name, color, dims in EMOTION_PROFILES:
            emotion = Emotion(name=name, color=color)
            session.add(emotion)
            await session.flush()
            dim = EmotionDimension(
                emotion_id=emotion.id,
                loudness=dims["loudness"],
                high_freq=dims["high_freq"],
                rhythm=dims["rhythm"],
                soundstage=dims["soundstage"],
                layering=dims["layering"],
                soothing=dims["soothing"],
                prosody=dims["prosody"],
            )
            session.add(dim)

        await session.commit()
        logger.info("已初始化 %d 种情绪 + 7 维模板", len(EMOTION_PROFILES))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(seed())