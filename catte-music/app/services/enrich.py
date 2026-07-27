"""数据增强服务：从 Apple Music API 批量补充歌曲流派、发行信息、编辑评论。"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.song import Song
from app.services.apple_music.auth import API_BASE, get_developer_token

logger = logging.getLogger(__name__)
STORE = "us"


async def _fetch_catalog_song(apple_music_id: str) -> dict | None:
    """从 Apple Music catalog 获取单首歌曲的完整元数据。"""
    dev_token = get_developer_token()
    headers = {"Authorization": f"Bearer {dev_token}"}
    async with httpx.AsyncClient(timeout=15.0) as cli:
        try:
            resp = await cli.get(
                f"{API_BASE}/v1/catalog/{STORE}/songs/{apple_music_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [{}])[0] if data.get("data") else None
        except httpx.HTTPError:
            return None


async def _fetch_catalog_album(apple_music_id: str) -> dict | None:
    """从 Apple Music catalog 获取专辑完整元数据。"""
    dev_token = get_developer_token()
    headers = {"Authorization": f"Bearer {dev_token}"}
    async with httpx.AsyncClient(timeout=15.0) as cli:
        try:
            resp = await cli.get(
                f"{API_BASE}/v1/catalog/{STORE}/albums/{apple_music_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [{}])[0] if data.get("data") else None
        except httpx.HTTPError:
            return None


def _extract_genres(catalog_data: dict) -> list[str]:
    """从 catalog 数据提取流派名称。"""
    attrs = catalog_data.get("attributes", catalog_data)
    return attrs.get("genreNames", [])


def _extract_editorial(catalog_data: dict) -> str | None:
    """提取 Apple Music editorial notes（标准版或短版）。"""
    attrs = catalog_data.get("attributes", catalog_data)
    notes = attrs.get("editorialNotes", {})
    return notes.get("standard") or notes.get("short")


def _extract_release_date(catalog_data: dict) -> str | None:
    """提取发行日期。"""
    attrs = catalog_data.get("attributes", catalog_data)
    return attrs.get("releaseDate")


def _extract_content_rating(catalog_data: dict) -> str | None:
    """提取内容分级。"""
    attrs = catalog_data.get("attributes", catalog_data)
    return attrs.get("contentRating")


async def enrich_song(db: AsyncSession, song: Song, enrich_album: bool = False) -> dict[str, Any]:
    """对单首歌曲进行数据增强，返回新增的字段 dict。"""
    apple_music_id = song.apple_music_id
    is_album = getattr(song, "type", "song") == "albums"

    # 根据类型调用不同的 catalog 端点
    catalog_data = None
    if is_album and enrich_album:
        catalog_data = await _fetch_catalog_album(apple_music_id)
        if catalog_data is None:
            catalog_data = await _fetch_catalog_song(apple_music_id)
    else:
        catalog_data = await _fetch_catalog_song(apple_music_id)

    if catalog_data is None:
        logger.warning("无法从 catalog 获取歌曲 #%d (%s)", song.id, song.title)
        return {}

    enriched: dict[str, Any] = {}

    # 流派
    genres = _extract_genres(catalog_data)
    if genres:
        enriched["genres"] = genres

    # 编辑评论
    editorial = _extract_editorial(catalog_data)
    if editorial:
        enriched["editorial_notes"] = editorial

    # 发行日期
    release_date = _extract_release_date(catalog_data)
    if release_date:
        enriched["release_date"] = release_date

    # 内容分级
    content_rating = _extract_content_rating(catalog_data)
    if content_rating:
        enriched["content_rating"] = content_rating

    # 合并到 raw_meta
    if song.raw_meta is None:
        song.raw_meta = {}
    song.raw_meta["_enriched"] = enriched

    logger.info(
        "歌曲 #%d (%s) 增强完成: genres=%s, editorial=%s",
        song.id, song.title, genres, "yes" if editorial else "no",
    )
    return enriched


async def batch_enrich(db: AsyncSession, limit: int = 50) -> dict[str, Any]:
    """批量增强数据库中缺少流派/编辑评论的歌曲。"""
    result = await db.execute(
        select(Song).order_by(Song.id.desc()).limit(limit)
    )
    songs = result.scalars().all()

    total = len(songs)
    enriched_count = 0
    errors = 0

    for song in songs:
        try:
            enriched = await enrich_song(db, song)
            if enriched:
                enriched_count += 1
        except Exception:
            logger.exception("增强歌曲 #%d 失败", song.id)
            errors += 1

    await db.commit()

    return {
        "total": total,
        "enriched": enriched_count,
        "errors": errors,
    }


# ── 简易文本情感分析（用于与 AI 情绪预测对比）──

# 情绪关键词映射
EMOTION_KEYWORDS: dict[str, list[str]] = {
    "甜蜜": ["sweet", "lovely", "tender", "adoring", "甜蜜", "可爱", "温柔"],
    "浪漫": ["romantic", "love", "passion", "heartfelt", "浪漫", "爱", "深情"],
    "治愈": ["healing", "comforting", "warm", "soothing", "治愈", "温暖", "安慰"],
    "悲伤": ["sad", "melancholy", "heartbreaking", "tear", "悲伤", "忧郁", "心碎"],
    "孤独": ["lonely", "isolated", "solitude", "alone", "孤独", "寂寞", "独白"],
    "深情": ["deep", "emotional", "soulful", "touching", "深情", "动人", "真挚"],
    "欢快": ["joyful", "happy", "upbeat", "cheerful", "欢快", "快乐", "活泼"],
    "愤怒": ["angry", "furious", "aggressive", "rage", "愤怒", "激烈", "狂暴"],
    "宁静": ["peaceful", "calm", "serene", "tranquil", "宁静", "平静", "安详"],
    "热血": ["epic", "powerful", "triumphant", "heroic", "热血", "激昂", "壮丽"],
    "忧郁": ["blue", "gloomy", "brooding", "dark", "忧郁", "阴沉", "惆怅"],
    "激昂": ["intense", "dramatic", "thrilling", "stirring", "激昂", "激烈", "震撼"],
    "松弛": ["relaxed", "laid-back", "chill", "easy", "松弛", "轻松", "随意"],
    "梦幻": ["dreamy", "ethereal", "floating", "airy", "梦幻", "缥缈", "空灵"],
    "震撼": ["shocking", "massive", "devastating", "overwhelming", "震撼", "磅礴", "恢弘"],
    "舒缓": ["gentle", "soft", "mellow", "smooth", "舒缓", "柔和", "轻柔"],
    "自由": ["free", "liberating", "soaring", "open", "自由", "奔放", "开阔"],
    "空灵": ["hollow", "spiritual", "crystalline", "heavenly", "空灵", "虚无", "透明"],
    "狂野": ["wild", "raw", "untamed", "fierce", "狂野", "粗犷", "奔放"],
    "迷幻": ["psychedelic", "trippy", "hypnotic", "trance", "迷幻", "催眠", "恍惚"],
}


def analyze_editorial_sentiment(editorial_text: str) -> dict[str, float]:
    """对编辑评论文本进行简易情绪关键词匹配，返回情绪得分 dict。"""
    text_lower = editorial_text.lower()
    scores: dict[str, float] = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        score = 0.0
        for kw in keywords:
            count = text_lower.count(kw.lower())
            if count > 0:
                score += count * 0.2  # 每个关键词命中 +0.2
        if score > 0:
            scores[emotion] = min(score, 1.0)
    return scores


def compare_sentiment_with_prediction(
    editorial_scores: dict[str, float],
    predicted_emotion: str,
    predicted_confidence: float,
) -> dict[str, Any]:
    """对比编辑评论情感分析与 AI 预测结果。"""
    editorial_match = editorial_scores.get(predicted_emotion, 0.0)
    top_editorial = max(editorial_scores, key=editorial_scores.get) if editorial_scores else "未知"

    return {
        "predicted_emotion": predicted_emotion,
        "predicted_confidence": predicted_confidence,
        "editorial_top_emotion": top_editorial,
        "editorial_match_score": editorial_match,
        "agreement": (
            "高度一致" if editorial_match > 0.5
            else "部分一致" if editorial_match > 0.2
            else "不一致"
        ),
        "editorial_scores": editorial_scores,
    }