"""AI 情绪分析路由。"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.prediction import AiPrediction
from app.models.song import Song, SongEmotion
from app.models.user import Emotion, User
from app.schemas.emotion import PredictionOut
from app.services.apple_music.auth import API_BASE, get_developer_token

router = APIRouter(prefix="/api", tags=["AI 分析"])

logger = logging.getLogger(__name__)
STORE = "us"


async def _search_preview(title: str, artist: str, limit: int = 3) -> str | None:
    """在 Apple Music catalog 搜索歌曲并返回第一个预览 URL。"""
    dev_token = get_developer_token()
    params = {"term": f"{title} {artist}", "limit": limit, "types": "songs"}
    headers = {"Authorization": f"Bearer {dev_token}"}
    async with httpx.AsyncClient(timeout=15.0) as cli:
        resp = await cli.get(
            f"{API_BASE}/v1/catalog/{STORE}/search",
            params=params, headers=headers,
        )
        resp.raise_for_status()
    data = resp.json()
    songs = data.get("results", {}).get("songs", {}).get("data", [])
    if not songs:
        return None
    for s in songs:
        if artist.lower() in s["attributes"]["artistName"].lower():
            previews = s["attributes"].get("previews", [])
            if previews:
                return previews[0]["url"]
    for s in songs:
        previews = s["attributes"].get("previews", [])
        if previews:
            return previews[0]["url"]
    return None


async def _download_preview(url: str, dest: Path) -> None:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as cli:
        resp = await cli.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    logger.info("预览音频已下载: %d bytes -> %s", len(resp.content), dest)


def _map_features_to_dimensions(features: "np.ndarray") -> "np.ndarray":  # noqa: F821
    """35 维音频特征 → 7 维情绪指标映射（响度/高频/节奏/声场/层次/舒缓/韵律）。

    特征布局：tempo, rmse, centroid, zcr, mfcc[13], chroma[12], tonnetz[6]
    """
    import numpy as np

    tempo, rmse, centroid, zcr = features[0], features[1], features[2], features[3]
    mfcc = features[4:17]       # 13 维
    chroma = features[17:29]    # 12 维
    tonnetz = features[29:35]   # 6 维

    # ── 7 维映射（chroma/tonnetz 增强）──

    loudness = min(100, max(0, rmse * 1000))

    # 高频：频谱质心 + MFCC 低阶均值 + chroma 高半音响应
    high_freq = min(100, max(0,
        (centroid / 5000) * 55 +
        float(np.mean(mfcc[:4])) * 5 +
        float(np.mean(chroma[6:])) * 35  # chroma 6-11 对应高半音
    ))

    rhythm = min(100, max(0, tempo * 0.8))

    # 声场：MFCC 中高阶标准差 + chroma 标准差（反映和声空间广度）
    soundstage = min(100, max(0,
        45 + float(np.std(mfcc[4:10])) * 3 +
        float(np.std(chroma)) * 20
    ))

    # 层次：MFCC 全阶标准差 + tonnetz 标准差（反映调性复杂度）
    layering = min(100, max(0,
        35 + float(np.std(mfcc)) * 4 +
        float(np.std(tonnetz)) * 15
    ))

    # 舒缓：反比于响度和高频，正比于 chroma 低频能量
    soothing = min(100, max(0,
        100 - rmse * 750 -
        (centroid / 5000) * 28 +
        float(np.mean(chroma[:4])) * 25  # 低半音越多越舒缓
    ))

    # 韵律：节奏变化 + MFCC 动态 + tonnetz 调性变化
    prosody = min(100, max(0,
        25 + float(np.std(mfcc[2:8])) * 3.5 +
        (zcr * 75) +
        float(np.std(tonnetz)) * 12
    ))

    return np.array([loudness, high_freq, rhythm, soundstage, layering, soothing, prosody])


def _classify_by_profile(
    features: "np.ndarray",  # noqa: F821
) -> tuple[str, float]:
    """基于 7 维情绪模板的最近邻分类器。"""
    import numpy as np
    from app.services.ai.seed_emotions import EMOTION_PROFILES

    audio_dim = _map_features_to_dimensions(features)

    best_emotion = "治愈"
    best_dist = float("inf")
    for name, _, dims in EMOTION_PROFILES:
        template = np.array([
            dims["loudness"], dims["high_freq"], dims["rhythm"],
            dims["soundstage"], dims["layering"], dims["soothing"], dims["prosody"],
        ])
        dist = np.linalg.norm(audio_dim - template)
        if dist < best_dist:
            best_dist = dist
            best_emotion = name

    confidence = max(0.0, min(1.0, 1.0 - best_dist / 150.0))
    return best_emotion, confidence


@router.post("/songs/{song_id}/analyze", response_model=PredictionOut)
async def analyze_song(
    song_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对歌曲进行 AI 情绪分析。

    试听音频来源：网易云歌曲优先取网易云官方试听（需绑定网易云账号），
    获取失败时回退 Apple Music catalog 预览；Apple Music 歌曲直接搜预览。
    """
    from app.services.ai.feature import extract_features

    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")

    # 收集候选试听源，按顺序依次尝试
    preview_urls: list[str] = []
    if getattr(song, "platform", "apple") == "netease":
        from app.services.netease import client as netease_client

        cookies = (
            netease_client.parse_cookie_str(user.netease_cookie)
            if user.netease_cookie
            else None
        )
        try:
            url = await netease_client.get_song_url(cookies, song.netease_id)
            if url:
                preview_urls.append(url)
        except Exception as exc:
            logger.warning("网易云试听获取失败（%s）: %s", song.title, exc)

    try:
        apple_url = await _search_preview(song.title, song.artist)
        if apple_url:
            preview_urls.append(apple_url)
    except httpx.HTTPError:
        logger.warning("Apple Music 预览搜索失败: %s", song.title)

    if not preview_urls:
        raise HTTPException(
            status_code=400,
            detail=f"未找到「{song.title}」的可试听音频，无法进行情绪分析",
        )

    features = None
    for preview_url in preview_urls:
        # 网易云为 mp3，Apple Music 为 m4a；后缀与内容匹配更稳
        suffix = ".mp3" if ".mp3" in preview_url.split("?")[0] else ".m4a"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            await _download_preview(preview_url, tmp_path)
            features = extract_features(tmp_path)
            break
        except Exception as exc:
            logger.warning("试听音频分析失败（%s）: %s", song.title, exc)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    if features is None:
        raise HTTPException(
            status_code=400,
            detail=f"「{song.title}」的试听音频无法解析，无法进行情绪分析",
        )

    emotion_name, confidence = _classify_by_profile(features)

    emotion_result = await db.execute(
        select(Emotion).where(Emotion.name == emotion_name)
    )
    emotion = emotion_result.scalar_one()
    color = emotion.color

    feature_dict = {str(i): float(features[i]) for i in range(len(features))}
    dims = _map_features_to_dimensions(features)
    db.add(AiPrediction(
        song_id=song.id, emotion_id=emotion.id,
        confidence=confidence, feature_vector=feature_dict,
        model_version="rule-based-v0.2",
        loudness=float(dims[0]), high_freq=float(dims[1]), rhythm=float(dims[2]),
        soundstage=float(dims[3]), layering=float(dims[4]), soothing=float(dims[5]),
        prosody=float(dims[6]),
    ))

    existing = await db.execute(
        select(SongEmotion).where(
            SongEmotion.song_id == song.id,
            SongEmotion.emotion_id == emotion.id,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(SongEmotion(
            song_id=song.id, emotion_id=emotion.id, confidence=confidence,
        ))

    await db.commit()
    logger.info("歌曲 #%d (%s) 分析完成: %s (%.2f%%)", song.id, song.title, emotion_name, confidence * 100)

    return PredictionOut(song_id=song.id, emotion=emotion_name, color=color, confidence=confidence)