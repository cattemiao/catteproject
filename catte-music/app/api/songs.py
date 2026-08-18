"""歌曲路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.song import Song
from app.models.user import User, UserFavorite
from app.schemas.song import FavoriteOut, SongListOut, SongOut
from app.services.apple_music.auth import API_BASE, get_developer_token
from app.api.analyze import _search_preview

import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/songs", tags=["歌曲"])


def _song_to_out(song: Song) -> SongOut:
    """Song ORM → SongOut，提取预览 URL 和封面图。"""
    preview_url = None
    artwork_url = None
    if song.raw_meta:
        try:
            if song.platform == "netease":
                # 网易云：封面在 raw_meta.cover_url
                artwork_url = song.raw_meta.get("cover_url")
                preview_url = song.raw_meta.get("preview_url")
            else:
                # Apple Music：单曲 attributes 下；专辑顶层
                attrs = song.raw_meta.get("attributes", song.raw_meta)
                previews = attrs.get("previews", [])
                if previews:
                    preview_url = previews[0].get("url")
                artwork = attrs.get("artwork", {})
                if artwork:
                    artwork_url = artwork.get("url", "").replace("{w}", "600").replace("{h}", "600")
        except (AttributeError, KeyError):
            pass
    return SongOut(
        id=song.id,
        apple_music_id=song.apple_music_id,
        platform=getattr(song, "platform", "apple") or "apple",
        netease_id=getattr(song, "netease_id", None),
        title=song.title,
        artist=song.artist,
        album=song.album,
        duration_ms=song.duration_ms,
        preview_url=preview_url,
        artwork_url=artwork_url,
        raw_meta=song.raw_meta,
        type=getattr(song, "type", "song") or "song",
        artist_bio=getattr(song, "artist_bio", None),
    )


@router.get("", response_model=SongListOut)
async def list_songs(
    q: str | None = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    platform: str | None = Query(None, description="apple/netease，默认全部"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Song).where(Song.user_id == user.id)
    count_query = select(func.count()).select_from(Song).where(Song.user_id == user.id)

    if platform:
        query = query.where(Song.platform == platform)
        count_query = count_query.where(Song.platform == platform)

    if q:
        query = query.where(Song.title.ilike(f"%{q}%") | Song.artist.ilike(f"%{q}%"))
        count_query = count_query.where(
            Song.title.ilike(f"%{q}%") | Song.artist.ilike(f"%{q}%")
        )

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(Song.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = [_song_to_out(s) for s in result.scalars().all()]
    return SongListOut(total=total, items=items)


@router.delete("")
async def clear_songs(
    platform: str = Query(..., description="apple/netease，必填"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空当前用户指定平台导入的歌曲（含情绪/标签/预测/收藏等关联数据），便于重新同步。"""
    from app.models.prediction import AiPrediction
    from app.models.song import SongEmotion, SongTag
    from app.models.user import UserFavorite

    song_ids = (
        await db.execute(
            select(Song.id).where(Song.user_id == user.id, Song.platform == platform)
        )
    ).scalars().all()
    if not song_ids:
        return {"deleted": 0, "platform": platform}

    # 先删关联数据（外键依赖），再删歌曲本体
    for model in (UserFavorite, SongEmotion, SongTag, AiPrediction):
        await db.execute(
            model.__table__.delete().where(model.song_id.in_(song_ids))
        )
    result = await db.execute(
        Song.__table__.delete().where(Song.id.in_(song_ids))
    )
    await db.commit()
    return {"deleted": result.rowcount, "platform": platform}


@router.get("/{song_id}", response_model=SongOut)
async def get_song(song_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    return _song_to_out(song)


@router.get("/{song_id}/preview")
async def get_song_preview(song_id: int, db: AsyncSession = Depends(get_db)):
    """获取歌曲的 Apple Music 预览音频 URL（实时搜索）。"""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    try:
        url = await _search_preview(song.title, song.artist)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Apple Music 搜索失败")
    if not url:
        raise HTTPException(status_code=404, detail="未找到预览音频")
    return {"preview_url": url, "title": song.title, "artist": song.artist}


@router.get("/{song_id}/review")
async def get_song_review(song_id: int, db: AsyncSession = Depends(get_db)):
    """获取歌曲评价（优先 Apple Music editorial notes，降级为基本信息描述）。"""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")

    # 尝试从 raw_meta 提取 editorial notes
    editorial = None
    if song.raw_meta:
        editorial = (
            song.raw_meta.get("editorialNotes", {})
            .get("standard", "")
            or song.raw_meta.get("editorialNotes", {})
            .get("short", "")
        )
    if editorial:
        return {
            "source": "Apple Music Editorial",
            "review": editorial,
        }

    # 降级：基本信息描述
    desc_parts = [f"{song.artist} 的作品"]
    if song.album:
        desc_parts.append(f"收录于专辑《{song.album}》")
    if song.duration_ms:
        mins = song.duration_ms // 60000
        secs = (song.duration_ms % 60000) // 1000
        desc_parts.append(f"时长 {mins}:{secs:02d}")
    return {
        "source": "基本信息",
        "review": "，".join(desc_parts) + "。",
    }


@router.get("/{song_id}/musicbrainz")
async def get_song_musicbrainz(song_id: int, db: AsyncSession = Depends(get_db)):
    """获取 MusicBrainz 权威音乐元数据（专辑/单曲均可）。"""
    from app.services.musicbrainz import fetch_musicbrainz_info

    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    # 播放列表在 MusicBrainz 无对应实体，直接返回未匹配
    if getattr(song, "type", "song") == "playlists":
        return {"found": False, "items": []}
    try:
        # 专辑页优先按专辑名匹配；单曲则退回歌曲名
        return await fetch_musicbrainz_info(song.album or song.title, song.artist)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="MusicBrainz 请求失败，请稍后重试")


@router.get("/{song_id}/album-tracks")
async def get_album_tracks(song_id: int, db: AsyncSession = Depends(get_db)):
    """专辑曲目：优先返回资料库同步时保存的曲目，否则从 Apple Music catalog 拉取。"""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    if getattr(song, "type", "song") != "albums":
        raise HTTPException(status_code=400, detail="该条目不是专辑")

    # 资料库同步的专辑自带曲目（relationships.tracks），无需请求 catalog
    lib_tracks = ((song.raw_meta or {}).get("relationships") or {}).get("tracks", {}).get("data", [])
    if lib_tracks:
        tracks = []
        for item in lib_tracks:
            attrs = item.get("attributes", {})
            tracks.append({
                "id": item.get("id"),
                "title": attrs.get("name", ""),
                "artist": attrs.get("artistName", ""),
                "duration_ms": attrs.get("durationInMillis"),
                "track_number": attrs.get("trackNumber"),
                "preview_url": None,
            })
        return {"album_title": song.title, "album_artist": song.artist, "tracks": tracks}

    dev_token = get_developer_token()
    headers = {"Authorization": f"Bearer {dev_token}"}
    async with httpx.AsyncClient(timeout=15.0) as cli:
        resp = await cli.get(
            f"{API_BASE}/v1/catalog/us/albums/{song.apple_music_id}/tracks",
            params={"limit": 50},
            headers=headers,
        )
        if resp.status_code == 404:
            # 资料库专辑 id 不是 catalog id，按 专辑名 + 艺术家 搜索 catalog 再拉曲目
            search_resp = await cli.get(
                f"{API_BASE}/v1/catalog/us/search",
                params={"term": f"{song.title} {song.artist}", "types": "albums", "limit": 5},
                headers=headers,
            )
            if search_resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Apple Music 曲目获取失败")
            albums = (search_resp.json().get("results") or {}).get("albums", {}).get("data", [])
            if not albums:
                raise HTTPException(status_code=404, detail="未找到该专辑的曲目")
            resp = await cli.get(
                f"{API_BASE}/v1/catalog/us/albums/{albums[0]['id']}/tracks",
                params={"limit": 50},
                headers=headers,
            )
        resp.raise_for_status()
    data = resp.json()
    tracks = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        previews = attrs.get("previews", [])
        tracks.append({
            "id": item["id"],
            "title": attrs.get("name", ""),
            "artist": attrs.get("artistName", ""),
            "duration_ms": attrs.get("durationInMillis"),
            "track_number": attrs.get("trackNumber"),
            "preview_url": previews[0]["url"] if previews else None,
        })
    return {"album_title": song.title, "album_artist": song.artist, "tracks": tracks}


@router.post("/{song_id}/favorite", response_model=FavoriteOut)
async def favorite_song(
    song_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Song).where(Song.id == song_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="歌曲不存在")
    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == user.id, UserFavorite.song_id == song_id
        )
    )
    if existing.scalar_one_or_none():
        return FavoriteOut(user_id=user.id, song_id=song_id, created_at="")
    fav = UserFavorite(user_id=user.id, song_id=song_id)
    db.add(fav)
    await db.commit()
    return FavoriteOut(user_id=user.id, song_id=song_id, created_at=str(fav.created_at))


# ── 数据增强与情感分析 ──

@router.post("/{song_id}/enrich")
async def enrich_song_endpoint(song_id: int, db: AsyncSession = Depends(get_db)):
    """对单首歌曲进行数据增强（流派、编辑评论等）。"""
    from app.services.enrich import enrich_song as _enrich

    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    try:
        enriched = await _enrich(db, song, enrich_album=True)
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"数据增强失败: {e}")
    return {"song_id": song_id, "enriched_fields": list(enriched.keys())}


@router.post("/enrich/batch")
async def batch_enrich_endpoint(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """批量数据增强。"""
    from app.services.enrich import batch_enrich

    try:
        result = await batch_enrich(db, limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"批量增强失败: {e}")
    return result


@router.get("/{song_id}/sentiment")
async def sentiment_analysis_endpoint(song_id: int, db: AsyncSession = Depends(get_db)):
    """对比编辑评论情感与 AI 情绪预测。"""
    from app.services.enrich import analyze_editorial_sentiment, compare_sentiment_with_prediction
    from app.models.prediction import AiPrediction
    from sqlalchemy.orm import joinedload

    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")

    # 获取编辑评论
    editorial_text = ""
    if song.raw_meta:
        enriched = song.raw_meta.get("_enriched", {})
        editorial_text = enriched.get("editorial_notes", "")
        if not editorial_text:
            # fallback: 从 raw_meta 直接提取
            editorial_text = (
                song.raw_meta.get("editorialNotes", {}).get("standard", "")
                or song.raw_meta.get("editorialNotes", {}).get("short", "")
            )

    editorial_scores = analyze_editorial_sentiment(editorial_text) if editorial_text else {}

    # 获取 AI 预测
    pred_result = await db.execute(
        select(AiPrediction)
        .where(AiPrediction.song_id == song_id)
        .options(joinedload(AiPrediction.emotion_rel))
        .order_by(AiPrediction.id.desc())
        .limit(1)
    )
    pred = pred_result.scalar_one_or_none()

    if not pred:
        return {
            "song_id": song_id,
            "editorial_scores": editorial_scores,
            "ai_prediction": None,
            "comparison": None,
            "message": "尚未进行 AI 分析",
        }

    comparison = compare_sentiment_with_prediction(
        editorial_scores, pred.emotion_rel.name, pred.confidence
    )

    return {
        "song_id": song_id,
        "editorial_scores": editorial_scores,
        "ai_prediction": {
            "emotion": pred.emotion_rel.name,
            "confidence": pred.confidence,
        },
        "comparison": comparison,
    }


# ── 外部反馈与模型优化 ──

@router.post("/{song_id}/feedback")
async def external_feedback_endpoint(song_id: int, db: AsyncSession = Depends(get_db)):
    """从 B 站等外部平台采集风格数据，与 AI 预测交叉验证。"""
    from app.services.feedback import collect_external_feedback

    try:
        feedback = await collect_external_feedback(db, song_id, force=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"外部反馈采集失败: {e}")
    return feedback


@router.post("/feedback/batch")
async def batch_feedback_endpoint(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """批量采集外部反馈。"""
    from app.services.feedback import batch_feedback

    try:
        result = await batch_feedback(db, limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"批量反馈失败: {e}")
    return result