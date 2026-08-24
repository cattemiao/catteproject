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
from app.services.ai import model as ai_model
from app.services.ai.feature import extract_features, map_to_dimensions, template_probs
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


def _classify_by_profile(features) -> dict:
    """模板最近邻兜底（模型缺失/加载失败时）。

    Returns:
        与 `model.predict` 同结构的 dict（probs 为模板伪概率）。
    """
    from app.services.ai.feature import template_distances

    distances = template_distances(features)
    best = min(distances, key=distances.get)
    confidence = max(0.0, min(1.0, 1.0 - distances[best] / 150.0))
    probs = template_probs(features)
    return {
        "primary": best,
        "confidence": confidence,
        "top_emotions": [
            {"name": name, "color": ai_model.EMOTION_COLORS.get(name, "#a855f7"), "prob": round(p, 4)}
            for name, p in sorted(probs.items(), key=lambda x: -x[1])[:3]
        ],
        "probs": {name: round(p, 4) for name, p in probs.items()},
        "fuzzy": False,
    }


def _classify(features) -> tuple[dict, str]:
    """v2 推理：多标签模型优先，缺失/异常 → 模板最近邻兜底。

    Returns:
        (result, model_version)
    """
    if ai_model.is_model_available():
        try:
            return ai_model.predict(features), ai_model.MODEL_VERSION
        except Exception as exc:
            logger.warning("多标签模型推理失败，回退模板最近邻: %s", exc)
    return _classify_by_profile(features), "rule-based-v0.2"


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
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")

    cookies = None
    if getattr(user, "netease_cookie", None):
        from app.services.netease import client as netease_client

        cookies = netease_client.parse_cookie_str(user.netease_cookie)
    return await analyze_song_core(song, db, cookies)


async def analyze_song_core(
    song: Song,
    db: AsyncSession,
    cookies: dict[str, str] | None = None,
) -> PredictionOut:
    """AI 情绪分析核心流程（路由与后台自动分析共用）。

    试听音频来源：网易云优先官方试听（后台任务无登录 cookie 时回退外链播放器），
    失败再回退 Apple Music catalog 预览。
    """
    # 收集候选试听源，按顺序依次尝试
    preview_urls: list[str] = []
    if getattr(song, "platform", "apple") == "netease":
        from app.services.netease import client as netease_client

        song_type = getattr(song, "type", "song") or "song"
        if song_type in ("albums", "playlists"):
            # 专辑/歌单没有独立音频，取其前几首单曲的试听作为情绪代表
            try:
                if song_type == "playlists":
                    tracks = await netease_client.get_playlist_tracks(
                        song.netease_id, cookies, limit=5
                    )
                else:
                    tracks = await netease_client.get_album_tracks(
                        song.netease_id, cookies, limit=5
                    )
            except Exception as exc:
                tracks = []
                logger.warning("网易云%s曲目获取失败（%s）: %s", song_type, song.title, exc)
            for track in tracks:
                tid = track.get("netease_id")
                if not tid:
                    continue
                try:
                    url = await netease_client.get_song_url(cookies, tid)
                    if url:
                        preview_urls.append(url)
                except Exception as exc:
                    logger.warning("网易云单曲试听获取失败（%s）: %s", track.get("title"), exc)
        else:
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

    result, model_version = _classify(features)
    emotion_name = result["primary"]
    confidence = result["confidence"]

    emotion_result = await db.execute(
        select(Emotion).where(Emotion.name == emotion_name)
    )
    emotion = emotion_result.scalar_one()
    color = emotion.color

    feature_dict = {str(i): float(features[i]) for i in range(len(features))}
    dims = map_to_dimensions(features)
    db.add(AiPrediction(
        song_id=song.id, emotion_id=emotion.id,
        confidence=confidence, feature_vector=feature_dict,
        emotion_probs=result["probs"],
        model_version=model_version,
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

    # top_emotions 与 GET /emotions/songs/{id}/emotion 保持一致：
    # 恒取概率 top-5（不足 5 时全量），保证点击分析后徽章立即显示齐全
    probs = result["probs"]
    ranked = sorted(probs.items(), key=lambda x: -x[1])[:5]
    top_emotions = [
        {
            "name": name,
            "color": color if name == emotion_name else ai_model.EMOTION_COLORS.get(name, "#a855f7"),
            "prob": round(float(prob), 4),
        }
        for name, prob in ranked
    ]

    return PredictionOut(
        song_id=song.id, emotion=emotion_name, color=color, confidence=confidence,
        top_emotions=top_emotions, probs=probs,
        fuzzy=result["fuzzy"], model_version=model_version,
    )