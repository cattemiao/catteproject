"""多标签弱标注管线（情绪算法 v2）。

职责：
1. 弱标注源聚合：B 站评论 / Apple Music 编辑评论 / 网易云歌单标签与评论 → {情绪: 得分}
2. 阈值转多标签（每源独立阈值）
3. 同曲多源加权投票仲裁（多标签允许冲突共存，仅单源低置信样本降噪丢弃）
4. 金标准导入（每情绪 10-30 首人工勾选 1-4 个情绪 + 主情绪，权重 ×5）
5. 训练集组装：X 特征矩阵 + Y 多标签矩阵 + sample_weight

数据格式：
- 弱标注：{song_key: {"scores": {emotion: score}, "sources": [...]}}
- 金标准：JSON 文件 [{ "key": "netease:123", "labels": ["治愈", "宁静"], "primary": "治愈" }]
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# 20 种情绪标签（与 seed_emotions.EMOTION_PROFILES 顺序一致，作为多标签分类的类空间）
EMOTION_LABELS = [
    "甜蜜", "浪漫", "治愈", "悲伤", "孤独", "深情", "欢快", "愤怒",
    "宁静", "热血", "忧郁", "激昂", "松弛", "梦幻", "震撼", "舒缓",
    "自由", "空灵", "狂野", "迷幻",
]

# 各弱标注源阈值（得分 ≥ 阈值 → 该情绪成为多标签之一）
WEAK_THRESHOLDS: dict[str, float] = {
    "bilibili": 0.3,
    "apple_editorial": 0.4,
    "netease_tags": 0.3,
    "netease_comments": 0.3,
}

# 各源仲裁权重（人工编辑 > 评论 > 标签）
SOURCE_WEIGHTS: dict[str, float] = {
    "bilibili": 1.0,
    "apple_editorial": 1.5,
    "netease_tags": 0.8,
    "netease_comments": 1.0,
}

# 金标准样本权重倍率
GOLD_WEIGHT_MULTIPLIER = 5.0

# 降噪：单源且最高合并得分低于该值 → 丢弃
MIN_SINGLE_SOURCE_CONF = 0.5


def song_key(song) -> str:
    """歌曲稳定键：platform:外部id。"""
    ext_id = getattr(song, "netease_id", None) or getattr(song, "apple_music_id", None)
    platform = getattr(song, "platform", "apple") or "apple"
    return f"{platform}:{ext_id}" if ext_id else f"{platform}:song-{getattr(song, 'id', '?')}"


def apply_threshold(scores: dict[str, float], threshold: float) -> set[str]:
    """得分 ≥ 阈值 → 多标签集合。"""
    return {e for e, s in scores.items() if s >= threshold}


def arbitrate(sources_scores: dict[str, dict[str, float]]) -> tuple[set[str], float] | None:
    """多源加权投票仲裁。

    Args:
        sources_scores: {source: {emotion: score}}（已过阈值筛选前传入原分）

    Returns:
        (labels, confidence) 或 None（降噪丢弃：仅单源且置信 < 0.5）
    """
    merged: dict[str, float] = {}
    for source, scores in sources_scores.items():
        weight = SOURCE_WEIGHTS.get(source, 1.0)
        for emotion, score in scores.items():
            merged[emotion] = merged.get(emotion, 0.0) + score * weight

    if not merged:
        return None

    total_weight = sum(SOURCE_WEIGHTS.get(s, 1.0) for s in sources_scores)
    max_score = max(merged.values())
    confidence = max_score / total_weight

    # 降噪：单源且置信 < 0.5 → 丢弃（样本不可靠）
    if len(sources_scores) == 1 and confidence < MIN_SINGLE_SOURCE_CONF:
        return None

    return set(merged.keys()), min(confidence, 1.0)


async def collect_weak_sources(db, song) -> dict[str, dict[str, float]]:
    """对单首歌曲采集所有可用弱标注源（网络爬虫）。

    Returns:
        {source: {emotion: score}}，失败的源不出现。
    """
    sources: dict[str, dict[str, float]] = {}
    title = getattr(song, "title", "") or ""
    artist = getattr(song, "artist", "") or ""

    # 1. B 站评论（搜索歌曲相关视频的评论情绪）
    try:
        from app.services.crawler.bilibili import get_bilibili_comment_consensus

        result = await get_bilibili_comment_consensus(title, artist)
        if result.get("scores"):
            sources["bilibili"] = result["scores"]
    except Exception as exc:
        logger.warning("B站弱标注失败 (%s): %s", title, exc)

    # 2. Apple Music 编辑评论（来自本地 raw_meta，无网络）
    try:
        from app.services.enrich import analyze_editorial_sentiment

        enriched = (getattr(song, "raw_meta", None) or {}).get("_enriched", {})
        editorial = enriched.get("editorial_notes", "")
        if not editorial:
            notes = (getattr(song, "raw_meta", None) or {}).get("editorialNotes", {})
            editorial = notes.get("standard", "") or notes.get("short", "")
        if editorial:
            scores = analyze_editorial_sentiment(editorial)
            if scores:
                sources["apple_editorial"] = scores
    except Exception as exc:
        logger.warning("Apple editorial 弱标注失败 (%s): %s", title, exc)

    # 3. 网易云标签 + 评论
    if getattr(song, "platform", None) == "netease" and getattr(song, "netease_id", None):
        try:
            from app.services.crawler.netease import (
                analyze_comment_sentiment,
                analyze_tags,
                get_hot_comments,
            )

            netease_id = str(song.netease_id)
            comments = await get_hot_comments(netease_id, limit=20)
            if comments:
                comment_scores = analyze_comment_sentiment(comments)
                if comment_scores:
                    sources["netease_comments"] = comment_scores
        except Exception as exc:
            logger.warning("网易云评论弱标注失败 (%s): %s", title, exc)
    else:
        # 非网易云歌曲：网易云搜索其标签作弱标注源
        try:
            from app.services.crawler.netease import analyze_tags, search_songs

            result = await search_songs(f"{title} {artist}", limit=3)
            for s in result.get("songs", [])[:3]:
                if s.get("title") and (s.get("title") in title or title in s.get("title", "")):
                    tags = s.get("tags", [])
                    tag_scores = analyze_tags(tags)
                    if tag_scores:
                        sources["netease_tags"] = tag_scores
                    break
        except Exception as exc:
            logger.warning("网易云标签弱标注失败 (%s): %s", title, exc)

    return sources


def weak_to_multilabel(
    song: Any, sources_scores: dict[str, dict[str, float]]
) -> dict[str, Any] | None:
    """弱标注 → 最终多标签（阈值 + 仲裁 + 降噪）。

    Returns:
        {"labels": [...], "confidence": float, "sources": [...]} 或 None
    """
    passed: dict[str, dict[str, float]] = {}
    for source, scores in sources_scores.items():
        threshold = WEAK_THRESHOLDS.get(source, 0.3)
        kept = {e: s for e, s in scores.items() if s >= threshold}
        if kept:
            passed[source] = kept

    result = arbitrate(passed)
    if result is None:
        return None
    labels, confidence = result
    # 过滤不在 20 类空间的情绪（爬虫关键词可能含风格映射）
    labels = {e for e in labels if e in EMOTION_LABELS}
    if not labels:
        return None
    return {
        "key": song_key(song),
        "labels": sorted(labels),
        "confidence": confidence,
        "sources": sorted(passed.keys()),
    }


def load_gold(path: str | Path) -> list[dict[str, Any]]:
    """加载金标准标注（JSON 数组或每行一个 JSON 对象）。

    格式: [{"key": "...", "labels": ["治愈","宁静"], "primary": "治愈"}, ...]
    """
    p = Path(path)
    if not p.exists():
        logger.warning("金标准文件不存在: %s", p)
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("gold", [])
    gold: list[dict[str, Any]] = []
    for item in data:
        labels = [e for e in item.get("labels", []) if e in EMOTION_LABELS]
        if not labels:
            continue
        gold.append({
            "key": item["key"],
            "labels": sorted(set(labels)),
            "primary": item.get("primary") if item.get("primary") in labels else labels[0],
            "weight": GOLD_WEIGHT_MULTIPLIER,
        })
    logger.info("金标准加载 %d 条", len(gold))
    return gold


def assemble_dataset(
    features_map: dict[str, np.ndarray],
    weak_samples: list[dict[str, Any]],
    gold_samples: list[dict[str, Any]] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """组装多标签训练集。

    Args:
        features_map: {song_key: 65 维特征向量}
        weak_samples: 弱标注样本 [{"key", "labels", "confidence", "sources"}]
        gold_samples: 金标准样本 [{"key", "labels", "primary", "weight"}]

    Returns:
        (X, Y, sample_weight, label_names)
        X: (n, 65)；Y: (n, 20) 二值多标签；sample_weight: (n,)
    """
    gold = gold_samples or []
    label_index = {name: i for i, name in enumerate(EMOTION_LABELS)}

    x_list: list[np.ndarray] = []
    y_list: list[list[int]] = []
    w_list: list[float] = []

    for sample in gold + weak_samples:
        key = sample["key"]
        features = features_map.get(key)
        if features is None:
            continue
        y = [0] * len(EMOTION_LABELS)
        for e in sample["labels"]:
            y[label_index[e]] = 1
        x_list.append(features)
        y_list.append(y)
        w_list.append(sample.get("weight", 1.0))

    if not x_list:
        raise ValueError("训练集为空：无特征与标注匹配的样本")

    return (
        np.array(x_list, dtype=float),
        np.array(y_list, dtype=int),
        np.array(w_list, dtype=float),
        EMOTION_LABELS,
    )
