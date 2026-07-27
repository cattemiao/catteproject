"""Bilibili 音乐风格采集器。

从 B 站搜索歌曲相关视频，提取标签、风格描述、简介中的情绪关键词，
用于补充和验证 AI 情绪预测模型。
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.parse
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.services.crawler.anti_crawl import random_delay, random_user_agent

logger = logging.getLogger(__name__)

BILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
BILI_COMMENT_API = "https://api.bilibili.com/x/v2/reply"


# ── 视频标签 → 音乐风格/情绪 映射 ──

TAG_TO_STYLE: dict[str, str] = {
    # 情绪类
    "治愈": "治愈",
    "伤感": "悲伤",
    "抒情": "深情",
    "燃": "热血",
    "燃向": "热血",
    "高燃": "热血",
    "热血": "热血",
    "激昂": "激昂",
    "震撼": "震撼",
    "唯美": "梦幻",
    "空灵": "空灵",
    "迷幻": "迷幻",
    "狂野": "狂野",
    "欢快": "欢快",
    "甜蜜": "甜蜜",
    "浪漫": "浪漫",
    "孤独": "孤独",
    "忧郁": "忧郁",
    "舒缓": "舒缓",
    "宁静": "宁静",
    "放松": "松弛",
    "自由": "自由",
    # 风格类
    "古风": "深情",
    "国风": "深情",
    "电音": "激昂",
    "电子": "激情",
    "摇滚": "狂野",
    "说唱": "狂野",
    "R&B": "松弛",
    "爵士": "松弛",
    "民谣": "舒缓",
    "纯音乐": "舒缓",
    "交响": "震撼",
    "古典": "舒缓",
    "二次元": "欢快",
    "ACG": "欢快",
    "动漫": "欢快",
    "游戏": "热血",
    "影视": "深情",
    "OST": "深情",
    "BGM": "舒缓",
    # 情绪强度
    "劲爆": "狂野",
    "洗脑": "欢快",
    "魔性": "迷幻",
    "催泪": "悲伤",
    "虐心": "悲伤",
    "温馨": "甜蜜",
    "轻快": "欢快",
    "清新": "自由",
    "慵懒": "松弛",
}

# 评论高频情绪词
COMMENT_EMOTION_WORDS: dict[str, list[str]] = {
    "治愈": ["治愈", "温暖", "温柔", "感动", "安抚"],
    "悲伤": ["哭了", "泪目", "破防", "心碎", "难受", "emo"],
    "热血": ["燃", "燃起来了", "热血沸腾", "鸡皮疙瘩", "头皮发麻", "爆炸"],
    "欢快": ["开心", "快乐", "好听", "单曲循环", "上头", "抖腿"],
    "深情": ["深情", "动人", "好听", "催泪", "感动", "表白"],
    "震撼": ["震撼", "炸裂", "神曲", "绝了", "封神", "太强了"],
    "自由": ["自由", "放飞", "解压", "舒服", "畅快"],
    "宁静": ["安静", "平静", "睡觉", "助眠", "放松", "发呆"],
    "梦幻": ["梦幻", "意境", "空灵", "仙", "绝美", "太美了"],
    "狂野": ["炸场", "嗨", "蹦迪", "甩头", "燃炸", "太爽了"],
}


def _build_search_query(title: str, artist: str) -> str:
    """构造 B 站搜索关键词。"""
    return f"{title} {artist}"


async def search_videos(
    query: str,
    page: int = 1,
    page_size: int = 20,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """搜索 B 站视频，返回结构化结果。"""
    headers = {
        "User-Agent": random_user_agent(),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    params = {
        "search_type": "video",
        "keyword": query,
        "page": page,
        "page_size": min(page_size, 50),
    }

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as cli:
        try:
            resp = await cli.get(BILI_SEARCH_API, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("B 站搜索失败: %s (%s)", query, exc)
            return {"videos": [], "total": 0, "error": str(exc)}

    result = data.get("data", {}).get("result", [])
    if isinstance(result, dict):
        result = result.get("video", []) or []

    videos = []
    for item in result:
        tag_raw = item.get("tag", "")
        tags = [t.strip() for t in tag_raw.split(",") if t.strip()] if tag_raw else []

        videos.append({
            "bvid": item.get("bvid"),
            "aid": item.get("aid"),
            "title": re.sub(r"<[^>]+>", "", item.get("title", "")),
            "description": item.get("description", ""),
            "tags": tags,
            "play": item.get("play", 0),
            "danmaku": item.get("video_review", 0),
            "favorites": item.get("favorites", 0),
            "duration": item.get("duration", ""),
            "author": item.get("author", ""),
            "pubdate": item.get("pubdate", 0),
        })

    return {
        "videos": videos,
        "total": data.get("data", {}).get("numResults", 0),
    }


def extract_style_tags(videos: list[dict]) -> dict[str, int]:
    """从 B 站视频标签中提取音乐风格标签并统计频次。

    返回 {风格标签: 出现次数}。
    """
    style_counts: dict[str, int] = {}

    for video in videos:
        title_tags = _extract_tags_from_text(video.get("title", ""))
        desc_tags = _extract_tags_from_text(video.get("description", ""))
        all_tags = video.get("tags", []) + title_tags + desc_tags

        for tag in all_tags:
            tag_lower = tag.lower().strip()
            if tag_lower in TAG_TO_STYLE:
                style = TAG_TO_STYLE[tag_lower]
                style_counts[style] = style_counts.get(style, 0) + 1
            elif tag in TAG_TO_STYLE:
                style = TAG_TO_STYLE[tag]
                style_counts[style] = style_counts.get(style, 0) + 1

    return style_counts


def _extract_tags_from_text(text: str) -> list[str]:
    """从文本中提取 #标签 和 【分类】。"""
    tags = re.findall(r"#(\S+)", text)
    tags += re.findall(r"【(.+?)】", text)
    tags += re.findall(r"\[(.+?)\]", text)
    return tags


async def get_song_external_styles(
    title: str,
    artist: str,
    max_pages: int = 3,
) -> dict[str, Any]:
    """获取歌曲的 B 站外部风格数据。

    多页搜索汇总标签统计。
    """
    query = _build_search_query(title, artist)
    all_videos: list[dict] = []
    total = 0

    for page in range(1, max_pages + 1):
        random_delay(0.5, 1.5)
        result = await search_videos(query, page=page, page_size=20)
        videos = result.get("videos", [])
        all_videos.extend(videos)
        total = max(total, result.get("total", 0))
        if len(videos) < 20:
            break

    style_counts = extract_style_tags(all_videos)

    # 按频次排序
    top_styles = sorted(style_counts.items(), key=lambda x: -x[1])
    primary_style = top_styles[0][0] if top_styles else None
    confidence = (top_styles[0][1] / sum(style_counts.values())) if style_counts else 0

    return {
        "query": query,
        "videos_found": len(all_videos),
        "total_results": total,
        "style_counts": {k: v for k, v in top_styles},
        "primary_style": primary_style,
        "confidence": round(confidence, 3),
        "source": "bilibili",
    }


async def get_song_comment_emotions(
    title: str,
    artist: str,
) -> dict[str, float]:
    """通过搜索结果标题/描述中的情绪关键词分析情绪倾向。

    返回 {情绪: 得分}。
    """
    query = _build_search_query(title, artist)
    result = await search_videos(query, page=1, page_size=10)
    videos = result.get("videos", [])

    text_pool = ""
    for v in videos:
        text_pool += v.get("title", "") + " "
        text_pool += v.get("description", "") + " "
        if hasattr(v.get("tags", []), "__iter__"):
            text_pool += " ".join(v.get("tags", [])) + " "

    emotion_scores: dict[str, float] = {}
    for emotion, words in COMMENT_EMOTION_WORDS.items():
        score = 0.0
        for word in words:
            count = text_pool.count(word)
            if count > 0:
                score += count * 0.15
        if score > 0:
            emotion_scores[emotion] = min(score, 1.0)

    return emotion_scores


async def fetch_video_comments(
    oid: int,
    page: int = 1,
    page_size: int = 20,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """获取 B 站视频评论。"""
    headers = {
        "User-Agent": random_user_agent(),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    params = {
        "type": 1,  # 视频评论
        "oid": oid,
        "pn": page,
        "ps": min(page_size, 20),
        "sort": 1,  # 按热度排序
    }

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as cli:
        try:
            resp = await cli.get(BILI_COMMENT_API, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("B站评论获取失败: oid=%d (%s)", oid, exc)
            return {"replies": [], "total": 0}

    replies = data.get("data", {}).get("replies", []) or []
    comments = []
    for r in replies:
        message = r.get("content", {}).get("message", "") if isinstance(r.get("content"), dict) else ""
        message = re.sub(r"<[^>]+>", "", message)
        if message:
            comments.append({
                "rpid": r.get("rpid"),
                "content": message,
                "like": r.get("like", 0),
                "ctime": r.get("ctime", 0),
            })

    return {
        "replies": comments,
        "total": data.get("data", {}).get("page", {}).get("count", 0) if data.get("data") else 0,
    }


def analyze_comment_emotions(comments: list[dict]) -> dict[str, float]:
    """分析评论列表中的情绪关键词得分。

    权重：点赞数加权（更热的评论权重更高）。
    """
    scores: dict[str, float] = {}
    total_weight = 0.0

    for c in comments:
        text = c.get("content", "")
        likes = c.get("like", 0)
        weight = 1.0 + min(likes / 100, 2.0)  # 点赞越多权重越大，上限 3x

        for emotion, words in COMMENT_EMOTION_WORDS.items():
            for word in words:
                count = text.count(word)
                if count > 0:
                    scores[emotion] = scores.get(emotion, 0) + count * 0.15 * weight
                    total_weight += weight

    # 归一化
    if total_weight > 0:
        for emotion in scores:
            scores[emotion] = min(scores[emotion] / max(1, total_weight / 3), 1.0)

    return scores


async def get_bilibili_comment_consensus(
    title: str,
    artist: str,
    max_videos: int = 3,
    comments_per_video: int = 20,
) -> dict[str, Any]:
    """从 B 站热门视频评论中提取情绪共识。

    流程：
    1. 搜索歌曲 → 取前 N 个视频
    2. 对每个视频取热门评论
    3. 汇总评论情绪得分
    """
    query = _build_search_query(title, artist)
    random_delay(0.5, 1.0)
    search_result = await search_videos(query, page=1, page_size=min(max_videos, 10))
    videos = search_result.get("videos", [])

    if not videos:
        return {
            "primary_emotion": None,
            "confidence": 0,
            "scores": {},
            "comments_found": 0,
            "source": "bilibili_comments",
        }

    all_comments: list[dict] = []
    for v in videos[:max_videos]:
        aid = v.get("aid", 0)
        if not aid:
            continue
        random_delay(0.5, 1.5)
        result = await fetch_video_comments(oid=aid, page=1, page_size=comments_per_video)
        all_comments.extend(result.get("replies", []))

    if not all_comments:
        return {
            "primary_emotion": None,
            "confidence": 0,
            "scores": {},
            "comments_found": 0,
            "source": "bilibili_comments",
        }

    scores = analyze_comment_emotions(all_comments)

    if not scores:
        return {
            "primary_emotion": None,
            "confidence": 0,
            "scores": {},
            "comments_found": len(all_comments),
            "sample_comments": [],
            "source": "bilibili_comments",
        }

    primary = max(scores, key=scores.get)
    confidence = scores[primary]

    # 挑选与主情绪契合的高赞评论作为典例
    primary_words = COMMENT_EMOTION_WORDS.get(primary, [])
    matched: list[dict] = []
    for c in all_comments:
        text = c.get("content", "")
        if any(w in text for w in primary_words):
            matched.append({
                "content": text,
                "like": c.get("like", 0),
                "emotion": primary,
            })
    # 按点赞排序，取前 5 条
    matched.sort(key=lambda x: -x.get("like", 0))
    sample_comments = matched[:5]

    return {
        "primary_emotion": primary,
        "confidence": round(confidence, 3),
        "scores": {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])},
        "comments_found": len(all_comments),
        "sample_comments": sample_comments,
        "source": "bilibili_comments",
    }