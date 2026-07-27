"""网易云音乐风格采集器。

搜索歌曲获取用户标签、热门评论情感，用于多源情绪共识验证。
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import httpx

from app.services.crawler.anti_crawl import random_delay, random_user_agent

logger = logging.getLogger(__name__)

NETEASE_SEARCH_URL = "https://music.163.com/api/search/get"
NETEASE_DETAIL_URL = "https://music.163.com/api/song/detail"
NETEASE_COMMENT_URL = "https://music.163.com/api/v1/resource/comments/R_SO_4_{song_id}"

# 网易云标签 → 情绪映射
NETEASE_TAG_TO_EMOTION: dict[str, str] = {
    "治愈": "治愈", "温暖": "治愈", "感动": "深情",
    "伤感": "悲伤", "寂寞": "孤独", "怀旧": "忧郁",
    "清新": "自由", "轻松": "松弛", "甜蜜": "甜蜜",
    "浪漫": "浪漫", "安静": "宁静", "空灵": "空灵",
    "梦幻": "梦幻", "震撼": "震撼", "史诗": "震撼",
    "激情": "激昂", "热血": "热血", "燃": "热血",
    "兴奋": "欢快", "快乐": "欢快", "动感": "欢快",
    "流行": "欢快", "摇滚": "狂野", "电子": "激昂",
    "民谣": "舒缓", "古典": "舒缓", "轻音乐": "舒缓",
    "爵士": "松弛", "R&B": "松弛", "说唱": "狂野",
    "中国风": "深情", "古风": "深情", "二次元": "欢快",
    "夜晚": "宁静", "学习": "宁静", "工作": "宁静",
    "运动": "热血", "旅行": "自由", "清晨": "自由",
    "思念": "深情", "孤独": "孤独",
}

# 评论情绪关键词
COMMENT_KEYWORDS: dict[str, list[str]] = {
    "治愈": ["治愈", "温暖", "温柔", "感动", "哭了", "好听"],
    "悲伤": ["哭了", "泪目", "破防", "心碎", "难受", "emo", "伤感"],
    "热血": ["燃", "燃起来了", "热血", "鸡皮疙瘩", "太燃了"],
    "欢快": ["开心", "快乐", "上头", "抖腿", "单曲循环", "摇摆"],
    "深情": ["深情", "动人", "表白", "思念", "想哭"],
    "震撼": ["震撼", "炸裂", "神曲", "绝了", "封神", "太强了", "鸡皮疙瘩"],
    "自由": ["自由", "解压", "舒服", "畅快", "放松"],
    "宁静": ["安静", "平静", "睡觉", "助眠", "发呆", "沉浸"],
    "梦幻": ["梦幻", "意境", "仙", "绝美", "太美了", "飘了"],
    "狂野": ["炸场", "嗨", "蹦迪", "太爽了", "带感"],
    "忧郁": ["忧郁", "惆怅", "失落", "沉思"],
    "激昂": ["激情", "澎湃", "热血沸腾", "气势", "磅礴"],
    "松弛": ["慵懒", "放松", "惬意", "chill", "舒服"],
    "舒缓": ["舒缓", "柔和", "温柔", "舒服", "放松"],
    "甜蜜": ["甜", "恋爱", "心动", "浪漫", "幸福"],
    "孤独": ["孤独", "一个人", "寂寞", "独处"],
}


def _build_query(title: str, artist: str) -> str:
    """构造搜索关键词。"""
    return f"{title} {artist}"


async def search_songs(
    query: str,
    limit: int = 10,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """搜索网易云音乐歌曲，返回基本信息+标签。"""
    headers = {
        "User-Agent": random_user_agent(),
        "Referer": "https://music.163.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    params = {
        "s": query,
        "type": 1,  # 单曲
        "limit": min(limit, 30),
        "offset": 0,
    }

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as cli:
        try:
            resp = await cli.post(NETEASE_SEARCH_URL, data=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("网易云搜索失败: %s (%s)", query, exc)
            return {"songs": [], "total": 0}

    songs = []
    result = data.get("result", {})
    items = result.get("songs", []) if isinstance(result, dict) else []

    for item in items:
        # 提取标签
        tags_raw = item.get("tags", "") or ""
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        # 从专辑 tags 补充
        album_tags = item.get("album", {}).get("tags", "") or ""
        tags += [t.strip() for t in album_tags.split(",") if t.strip()] if album_tags else []

        # 从别名/转义名提取风格
        alias = item.get("alias", [])
        trans_names = item.get("transNames", [])

        songs.append({
            "netease_id": str(item.get("id", "")),
            "title": item.get("name", ""),
            "artist": ", ".join([a.get("name", "") for a in item.get("artists", [])]),
            "album": item.get("album", {}).get("name", ""),
            "tags": tags,
            "alias": alias,
            "duration": item.get("duration", 0),
            "popularity": item.get("popularity", 0),
            "score": item.get("score", 0),
        })

    return {"songs": songs, "total": result.get("songCount", 0) if isinstance(result, dict) else 0}


async def get_hot_comments(
    netease_song_id: str,
    limit: int = 20,
    timeout: float = 15.0,
) -> list[dict[str, Any]]:
    """获取网易云歌曲热门评论（含点赞数）。"""
    headers = {
        "User-Agent": random_user_agent(),
        "Referer": "https://music.163.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    url = NETEASE_COMMENT_URL.format(song_id=netease_song_id)
    params = {"limit": min(limit, 20), "offset": 0}

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as cli:
        try:
            resp = await cli.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("网易云评论获取失败: song_id=%s (%s)", netease_song_id, exc)
            return []

    comments = []
    hot_comments = data.get("hotComments", []) or data.get("comments", [])

    for c in hot_comments[:limit]:
        content = c.get("content", "")
        if content:
            comments.append({
                "content": re.sub(r"<[^>]+>", "", content),
                "like": c.get("likedCount", 0) or c.get("likeCount", 0),
            })

    return comments


def analyze_tags(tags: list[str]) -> dict[str, float]:
    """将网易云标签映射为情绪得分。"""
    scores: dict[str, float] = {}
    for tag in tags:
        tag_clean = tag.strip()
        if tag_clean in NETEASE_TAG_TO_EMOTION:
            emotion = NETEASE_TAG_TO_EMOTION[tag_clean]
            scores[emotion] = scores.get(emotion, 0.0) + 0.25
    return {k: min(v, 1.0) for k, v in scores.items()}


def analyze_comment_sentiment(comments: list[dict[str, Any]]) -> dict[str, float]:
    """分析评论中的情绪关键词。"""
    text = " ".join(c.get("content", "") for c in comments)
    scores: dict[str, float] = {}

    for emotion, keywords in COMMENT_KEYWORDS.items():
        score = 0.0
        for kw in keywords:
            count = text.count(kw)
            if count > 0:
                score += count * 0.15
        if score > 0:
            scores[emotion] = min(score, 1.0)

    return scores


async def get_netease_consensus(
    title: str,
    artist: str,
) -> dict[str, Any]:
    """获取网易云音乐的综合情绪共识。

    返回：
        - primary_emotion: 最高票情绪
        - confidence: 置信度 (0-1)
        - tag_scores: 标签情绪得分
        - comment_scores: 评论情绪得分
        - comments_found: 评论数量
    """
    query = _build_query(title, artist)
    search_result = await search_songs(query, limit=5)

    songs = search_result.get("songs", [])
    if not songs:
        return {
            "primary_emotion": None,
            "confidence": 0,
            "tag_scores": {},
            "comment_scores": {},
            "comments_found": 0,
            "sample_comments": [],
            "source": "netease",
            "has_data": False,
        }

    # 取最佳匹配
    best_song = songs[0]
    tags = best_song.get("tags", [])

    # 标签情绪得分
    tag_scores = analyze_tags(tags)

    # 获取热门评论
    random_delay(0.5, 1.0)
    comments = await get_hot_comments(best_song.get("netease_id", ""), limit=20)
    comment_scores = analyze_comment_sentiment(comments)

    # 合并得分：标签权重 0.4 + 评论权重 0.6
    combined: dict[str, float] = {}
    for emotion, score in tag_scores.items():
        combined[emotion] = combined.get(emotion, 0) + score * 0.4
    for emotion, score in comment_scores.items():
        combined[emotion] = combined.get(emotion, 0) + score * 0.6

    if not combined:
        return {
            "primary_emotion": None,
            "confidence": 0,
            "tag_scores": tag_scores,
            "comment_scores": comment_scores,
            "comments_found": len(comments),
            "sample_comments": [],
            "source": "netease",
            "has_data": False,
        }

    # 主情绪
    primary = max(combined, key=combined.get)
    confidence = combined[primary]
    confidence = min(confidence, 1.0)

    # 挑选与主情绪契合的高赞评论作为典例
    primary_words = COMMENT_KEYWORDS.get(primary, [])
    matched: list[dict] = []
    for c in comments:
        text = c.get("content", "")
        if any(w in text for w in primary_words):
            matched.append({
                "content": text,
                "like": c.get("like", 0),
                "emotion": primary,
            })
    matched.sort(key=lambda x: -x.get("like", 0))
    sample_comments = matched[:5]

    return {
        "primary_emotion": primary,
        "confidence": round(confidence, 3),
        "tag_scores": tag_scores,
        "comment_scores": comment_scores,
        "comments_found": len(comments),
        "sample_comments": sample_comments,
        "all_scores": {k: round(v, 3) for k, v in sorted(combined.items(), key=lambda x: -x[1])},
        "source": "netease",
        "has_data": True,
    }