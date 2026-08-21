"""多标签训练数据采集脚本（情绪算法 v2，CPU）。

流程（真实模式）：
    情绪关键词 → 网易云搜索单曲（无需登录）→ 采样 N 首
    → 下载 30s 试听音频 → 65 维特征提取
    → 弱标注（网易云标签/评论 + B 站评论；Apple editorial 仅库内歌曲可用）
    → 阈值转多标签 + 多源仲裁 → 输出训练集

输出目录（--out，默认 data/raw/emotion_dataset_v2/）：
    features.npy    # (n, 65) 特征矩阵
    labels.json     # [{key, labels, confidence, sources}]
    songs.json      # [{key, title, artist, album}]
    stats.json      # 统计（总数/每情绪样本数/跳过原因）

用法：
    python -m app.services.ai.collect_v2 --keywords 治愈,悲伤,欢快 --count 60
    python -m app.services.ai.collect_v2 --synthetic --count 200   # 合成数据（跑通训练管线）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import tempfile
from pathlib import Path

import httpx
import numpy as np

from app.services.ai.feature import FEATURE_DIM, extract_features
from app.services.ai.labeling import (
    EMOTION_LABELS,
    collect_weak_sources,
    song_key,
    weak_to_multilabel,
)

logger = logging.getLogger(__name__)

SYNTHETIC_MEAN_PROFILE: dict[str, list[float]] = {}


def _synth_profile(name: str) -> list[float]:
    """基于 7 维情绪模板生成 65 维合成特征的中心点（粗映射，仅供管线联调）。"""
    from app.services.ai.seed_emotions import EMOTION_PROFILES

    if name not in SYNTHETIC_MEAN_PROFILE:
        profile = next((p for n, _, p in EMOTION_PROFILES if n == name), None)
        dims = [
            profile["loudness"], profile["high_freq"], profile["rhythm"],
            profile["soundstage"], profile["layering"], profile["soothing"],
            profile["prosody"],
        ] if profile else [50.0] * 7
        # 35 维旧布局 → 65 维新布局粗略映射（仅保证维度一致，供测试训练往返）
        vec: list[float] = []
        vec += [dims[2], dims[0] / 100.0, 0.5, 0.1]           # tempo/rmse/centroid/zcr 粗值
        vec += [0.5, 5000.0 * dims[1] / 100.0, 0.6, 0.3]       # flatness/rolloff/entropy/onset
        vec += [dims[0] / 8.0] * 13                            # mfcc mean（响度相关）
        vec += [0.3] * 13                                      # mfcc std
        vec += [0.05] * 13                                     # delta mfcc mean
        vec += [dims[4] / 12.0] * 12                           # chroma（层次相关）
        vec += [dims[3] / 20.0] * 6                            # tonnetz（声场相关）
        SYNTHETIC_MEAN_PROFILE[name] = vec
    return SYNTHETIC_MEAN_PROFILE[name]


def _synthetic_sample(name: str) -> np.ndarray:
    center = np.array(_synth_profile(name))
    return np.clip(center + np.random.default_rng().normal(0, 1.2, FEATURE_DIM), 0, None)


def _pick_keywords(kw: str) -> list[str]:
    return [k.strip() for k in kw.split(",") if k.strip()]


async def _download(url: str, dest: Path) -> None:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as cli:
        resp = await cli.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)


async def _collect_netease_sample(
    keyword: str, limit: int, rng: random.Random
) -> list[dict]:
    from app.services.crawler.netease import search_songs

    result = await search_songs(keyword, limit=limit)
    return result.get("songs", [])


async def _weak_and_features(
    song: dict, out_dir: Path
) -> tuple[str, np.ndarray | None, dict | None]:
    """下载试听 → 特征 + 弱标注。返回 (key, features, sample)。"""
    from app.services.netease.client import get_song_url

    netease_id = str(song["netease_id"])
    key = f"netease:{netease_id}"

    # 弱标注（无需音频，先做；特征失败不影响标注收集）
    sample = await _weak_netease_annotate(song, key)

    # 下载试听音频（weapi 无 cookie 可能失败，兜底外链）
    url = await get_song_url({}, netease_id)
    if not url:
        return key, None, sample

    suffix = ".mp3" if "url?id=" in url or ".mp3" in url else ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        await _download(url, tmp_path)
        if tmp_path.stat().st_size < 4096:
            return key, None, sample
        features = extract_features(tmp_path)
        return key, features, sample
    except Exception as exc:
        logger.warning("特征提取失败 %s (%s): %s", song.get("title"), key, exc)
        return key, None, sample
    finally:
        tmp_path.unlink(missing_ok=True)


async def _weak_netease_annotate(song: dict, key: str) -> dict | None:
    """对网易云歌曲做弱标注（标签 + 热门评论）。"""
    from app.services.crawler.netease import (
        analyze_comment_sentiment,
        analyze_tags,
        get_hot_comments,
    )

    sources: dict[str, dict[str, float]] = {}
    tags = song.get("tags", [])
    if tags:
        tag_scores = analyze_tags(tags)
        if tag_scores:
            sources["netease_tags"] = tag_scores
    try:
        comments = await get_hot_comments(song["netease_id"], limit=20)
        if comments:
            comment_scores = analyze_comment_sentiment(comments)
            if comment_scores:
                sources["netease_comments"] = comment_scores
    except Exception as exc:
        logger.warning("网易云评论弱标注失败 (%s): %s", song.get("title"), exc)

    if not sources:
        return None
    dummy = type("SongStub", (), {"netease_id": song["netease_id"], "platform": "netease"})()
    return weak_to_multilabel(dummy, sources)


async def collect_real(
    keywords: list[str], count: int, out_dir: Path, per_keyword: int
) -> None:
    """真实数据采集：网易云搜索 + 试听下载 + 特征 + 弱标注。"""
    rng = random.Random(42)
    seen: set[str] = set()
    songs_meta: list[dict] = []
    samples: list[dict] = []
    features_map: dict[str, np.ndarray] = {}

    for kw in keywords:
        fetched = await _collect_netease_sample(kw, limit=per_keyword * 2, rng=rng)
        rng.shuffle(fetched)
        for song in fetched:
            netease_id = str(song.get("netease_id", ""))
            if not netease_id or netease_id in seen:
                continue
            seen.add(netease_id)
            key, features, sample = await _weak_and_features(song, out_dir)
            if sample and features is not None:
                features_map[key] = features
                samples.append(sample)
                songs_meta.append({
                    "key": key, "title": song.get("title"),
                    "artist": song.get("artist"), "album": song.get("album"),
                })
            if len(samples) >= count:
                break
        if len(samples) >= count:
            break

    _dump_dataset(out_dir, features_map, samples, songs_meta)


def collect_synthetic(count: int, out_dir: Path) -> None:
    """合成数据：按 20 类模板中心加噪生成特征 + 多标签（主情绪 + 随机 1 个次情绪）。"""
    rng = np.random.default_rng(42)
    features_map: dict[str, np.ndarray] = {}
    samples: list[dict] = []
    songs_meta: list[dict] = []

    per_class = max(1, count // len(EMOTION_LABELS))
    for i, name in enumerate(EMOTION_LABELS):
        for j in range(per_class):
            key = f"syn:{i}-{j}"
            features_map[key] = _synthetic_sample(name)
            labels = {name}
            # 随机附加一个次情绪（概率 40%）
            if rng.random() < 0.4:
                other = EMOTION_LABELS[(i + 3) % len(EMOTION_LABELS)]
                labels.add(other)
            samples.append({
                "key": key,
                "labels": sorted(labels),
                "confidence": round(float(rng.uniform(0.6, 0.95)), 3),
                "sources": ["synthetic"],
            })
            songs_meta.append({"key": key, "title": f"合成样本 {i}-{j}", "artist": name, "album": ""})

    _dump_dataset(out_dir, features_map, samples, songs_meta)


def _dump_dataset(
    out_dir: Path,
    features_map: dict[str, np.ndarray],
    samples: list[dict],
    songs_meta: list[dict],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = [s["key"] for s in samples]
    X = np.stack([features_map[k] for k in keys])
    np.save(out_dir / "features.npy", X)
    (out_dir / "labels.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "songs.json").write_text(
        json.dumps(songs_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    per_emotion = {name: 0 for name in EMOTION_LABELS}
    for s in samples:
        for e in s["labels"]:
            per_emotion[e] = per_emotion.get(e, 0) + 1
    stats = {
        "total": len(samples),
        "dim": int(X.shape[1]),
        "per_emotion": per_emotion,
    }
    (out_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("训练集已导出: %s (%d 样本, %d 维)", out_dir, len(samples), X.shape[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="多标签训练数据采集")
    parser.add_argument("--keywords", type=str, default="治愈,悲伤,欢快,宁静,热血",
                        help="网易云搜索关键词（逗号分隔）")
    parser.add_argument("--count", type=int, default=60, help="目标样本数")
    parser.add_argument("--out", type=Path, default=Path("data/raw/emotion_dataset_v2"))
    parser.add_argument("--synthetic", action="store_true", help="生成合成数据（跑通管线）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.synthetic:
        collect_synthetic(args.count, args.out)
        return

    per_keyword = max(5, args.count // max(len(_pick_keywords(args.keywords)), 1))
    asyncio.run(collect_real(_pick_keywords(args.keywords), args.count, args.out, per_keyword))


if __name__ == "__main__":
    main()
