"""网易云音乐路由：二维码登录、最近播放同步、搜索。"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.songs import _song_to_out
from app.database import get_db
from app.models.song import Song
from app.models.user import User
from app.schemas.song import SongOut
from app.services.netease import client as netease_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/netease", tags=["网易云"])


@router.post("/qr")
async def create_qr():
    """生成网易云扫码登录二维码。"""
    return await netease_client.create_qr_key()


@router.get("/qr/{key}")
async def check_qr(key: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """轮询扫码状态。code=803 表示成功，同时把 cookie 保存到用户。"""
    # 用户可能已有 cookie，带上一起请求
    prev = netease_client.parse_cookie_str(user.netease_cookie or "") if user.netease_cookie else None
    result = await netease_client.check_qr_status(key, prev_cookies=prev)

    if result.get("code") == netease_client.QR_SUCCESS and result.get("cookies"):
        # 保存登录态
        cookie_str = "; ".join(f"{k}={v}" for k, v in result["cookies"].items())
        user.netease_cookie = cookie_str
        profile = result.get("profile", {})
        user.netease_profile = profile
        user.netease_uid = str(profile.get("userId") or "") or None
        await db.commit()
        result["nickname"] = profile.get("nickname", "")
        result["avatar_url"] = profile.get("avatarUrl", "")

    # 不再返回完整 cookie 给前端，避免泄露
    result.pop("cookies", None)
    return result


@router.get("/status")
async def status(user: User = Depends(get_current_user)):
    """当前用户网易云绑定状态。"""
    if not user.netease_cookie:
        return {"bound": False}
    profile = user.netease_profile or {}
    return {
        "bound": True,
        "nickname": profile.get("nickname", ""),
        "avatar_url": profile.get("avatarUrl", ""),
        "uid": user.netease_uid,
    }


@router.post("/sync")
async def sync_recent(
    limit: int = Query(10, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """同步网易云最近播放记录到本地库，并触发后台情绪分析。"""
    if not user.netease_cookie:
        raise HTTPException(status_code=401, detail="尚未绑定网易云账号")
    if not user.netease_uid:
        raise HTTPException(status_code=400, detail="缺少网易云用户信息，请重新扫码登录")

    cookies = netease_client.parse_cookie_str(user.netease_cookie)
    try:
        songs_data = await netease_client.get_recent_played(cookies, int(user.netease_uid), limit=limit)
    except Exception as exc:
        logger.warning("网易云最近播放获取失败: %s", exc)
        raise HTTPException(status_code=502, detail="网易云接口请求失败，可能是登录已过期，请重新扫码")

    created = []
    for item in songs_data:
        song_id = str(item.get("netease_id", ""))
        if not song_id:
            continue
        # 去重：该用户下 netease_id 已存在则跳过
        exists = await db.execute(
            select(Song).where(
                Song.platform == "netease",
                Song.netease_id == song_id,
                Song.user_id == user.id,
            )
        )
        if exists.scalar_one_or_none():
            continue

        raw_meta = {
            **item.get("raw", {}),
            "cover_url": item.get("cover_url", ""),
            "preview_url": item.get("preview_url", ""),
        }
        song = Song(
            apple_music_id=f"netese-{user.id}-{song_id}",
            platform="netease",
            netease_id=song_id,
            user_id=user.id,
            title=item.get("title", "")[:256],
            artist=item.get("artist", "")[:256],
            album=(item.get("album") or "")[:256],
            duration_ms=item.get("duration_ms"),
            type="song",
            raw_meta=raw_meta,
        )
        db.add(song)
        await db.flush()
        created.append(song)

    await db.commit()

    # 后台触发情绪分析与多源评价（与 Apple Music 同步流程一致），不阻塞接口响应
    if created:
        from app.api.apple_music import _background_enrich

        background_tasks.add_task(_background_enrich, [s.id for s in created])

    return {
        "synced": len(created),
        "total_in_db": len(created) + len(songs_data),
        "songs": [_song_to_out(s) for s in created],
    }


@router.get("/library")
async def sync_library(
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """同步网易云音乐库（收藏的专辑 + 收藏的歌单）到本地库，便于浏览完整收藏。"""
    if not user.netease_cookie:
        raise HTTPException(status_code=401, detail="尚未绑定网易云账号")
    if not user.netease_uid:
        raise HTTPException(status_code=400, detail="缺少网易云用户信息，请重新扫码登录")

    cookies = netease_client.parse_cookie_str(user.netease_cookie)
    try:
        albums = await netease_client.get_subscribed_albums(cookies, limit=limit)
        playlists = await netease_client.get_subscribed_playlists(cookies, int(user.netease_uid), limit=limit)
    except Exception as exc:
        logger.warning("网易云音乐库获取失败: %s", exc)
        raise HTTPException(status_code=502, detail="网易云接口请求失败，可能是登录已过期，请重新扫码")

    created_albums: list[Song] = []
    for item in albums:
        album_id = item.get("netease_id", "")
        if not album_id:
            continue
        # 去重：该用户下 netease_id 已存在则跳过
        exists = await db.execute(
            select(Song).where(
                Song.platform == "netease",
                Song.netease_id == album_id,
                Song.user_id == user.id,
            )
        )
        if exists.scalar_one_or_none():
            continue

        raw_meta = {
            **item.get("raw", {}),
            "cover_url": item.get("cover_url", ""),
            "publish_time": item.get("publish_time"),
            "track_count": item.get("track_count"),
        }
        song = Song(
            apple_music_id=f"netese-{user.id}-{album_id}",
            platform="netease",
            netease_id=album_id,
            user_id=user.id,
            title=(item.get("title") or "")[:256],
            artist=(item.get("artist") or "")[:256],
            album=(item.get("album") or "")[:256],
            type="albums",
            raw_meta=raw_meta,
        )
        db.add(song)
        await db.flush()
        created_albums.append(song)

    created_playlists: list[Song] = []
    for item in playlists:
        pl_id = item.get("netease_id", "")
        if not pl_id:
            continue
        # 去重：该用户下 netease_id 已存在则跳过
        exists = await db.execute(
            select(Song).where(
                Song.platform == "netease",
                Song.netease_id == pl_id,
                Song.user_id == user.id,
            )
        )
        if exists.scalar_one_or_none():
            continue

        raw_meta = {
            **item.get("raw", {}),
            "cover_url": item.get("cover_url", ""),
            "track_count": item.get("track_count"),
        }
        song = Song(
            apple_music_id=f"netese-{user.id}-{pl_id}",
            platform="netease",
            netease_id=pl_id,
            user_id=user.id,
            title=(item.get("title") or "")[:256],
            artist=(item.get("artist") or "")[:256],
            album=(item.get("album") or "")[:256],
            type="playlists",
            raw_meta=raw_meta,
        )
        db.add(song)
        await db.flush()
        created_playlists.append(song)

    await db.commit()

    return {
        "synced": len(created_albums) + len(created_playlists),
        "albums": [_song_to_out(s) for s in created_albums],
        "playlists": [_song_to_out(s) for s in created_playlists],
    }


@router.get("/track-url")
async def get_track_url(
    netease_id: str = Query(..., min_length=1),
    user: User = Depends(get_current_user),
):
    """按网易云歌曲 id 获取试听音频 URL（用于专辑/歌单曲目行试听）。"""
    if not user.netease_cookie:
        raise HTTPException(status_code=401, detail="尚未绑定网易云账号")
    cookies = netease_client.parse_cookie_str(user.netease_cookie)
    try:
        url = await netease_client.get_song_url(cookies, netease_id)
    except Exception as exc:
        logger.warning("网易云单曲试听获取失败: %s", exc)
        raise HTTPException(status_code=502, detail="网易云接口请求失败，可能是登录已过期，请重新扫码")
    if not url:
        raise HTTPException(status_code=404, detail="未获取到该歌曲的试听音频")
    return {"preview_url": url}


@router.get("/preview/{song_id}")
async def get_preview(
    song_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取网易云歌曲的试听音频 URL（实时获取，URL 有时效）。"""
    if not user.netease_cookie:
        raise HTTPException(status_code=401, detail="尚未绑定网易云账号")
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    if song.platform != "netease" or not song.netease_id:
        raise HTTPException(status_code=400, detail="该歌曲不是网易云歌曲")

    cookies = netease_client.parse_cookie_str(user.netease_cookie)
    try:
        url = await netease_client.get_song_url(cookies, song.netease_id)
    except Exception as exc:
        logger.warning("网易云试听获取失败: %s", exc)
        raise HTTPException(status_code=502, detail="网易云接口请求失败，可能是登录已过期，请重新扫码")
    if not url:
        raise HTTPException(status_code=404, detail="未获取到该歌曲的试听音频")
    return {"preview_url": url, "title": song.title, "artist": song.artist}


@router.get("/search", response_model=list[SongOut])
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索网易云歌曲并入库。"""
    results = await netease_client.search_songs(q, limit=limit)
    saved = []
    for item in results:
        song_id = str(item.get("netease_id", ""))
        exists = await db.execute(
            select(Song).where(
                Song.platform == "netease",
                Song.netease_id == song_id,
                Song.user_id == user.id,
            )
        )
        song = exists.scalar_one_or_none()
        if not song:
            song = Song(
                apple_music_id=f"netese-{user.id}-{song_id}",
                platform="netease",
                netease_id=song_id,
                user_id=user.id,
                title=item.get("title", "")[:256],
                artist=item.get("artist", "")[:256],
                album=(item.get("album") or "")[:256],
                duration_ms=item.get("duration_ms"),
                type="song",
                raw_meta={**item.get("raw", {}), "cover_url": item.get("cover_url", ""), "preview_url": ""},
            )
            db.add(song)
            await db.flush()
        saved.append(song)
    await db.commit()
    return [_song_to_out(s) for s in saved]
