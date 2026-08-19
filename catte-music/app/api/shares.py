"""分享与点赞路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.songs import _song_to_out
from app.database import get_db
from app.models.prediction import AiPrediction
from app.models.share import Like, Share
from app.models.song import Song
from app.models.user import User
from app.schemas.share import LikeOut, ShareCreate, ShareOut, ShareStatus

router = APIRouter(prefix="/api/shares", tags=["分享"])


def _share_to_out(
    share: Share,
    song: Song,
    sharer: User,
    like_count: int,
    user_liked: bool,
    emotion: str | None = None,
    similarity: float | None = None,
) -> ShareOut:
    return ShareOut(
        id=share.id,
        song=_song_to_out(song),
        sharer_id=sharer.id,
        sharer_username=sharer.username,
        platform=share.platform,
        comment=share.comment,
        like_count=like_count,
        user_liked=user_liked,
        created_at=share.created_at,
        emotion=emotion,
        similarity=similarity,
    )


@router.get("/status", response_model=ShareStatus)
async def share_status(
    song_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户是否已分享指定歌曲（用于页面刷新后恢复按钮状态）。"""
    exist = (
        await db.execute(
            select(Share.id).where(Share.user_id == user.id, Share.song_id == song_id).limit(1)
        )
    ).scalar_one_or_none()
    return ShareStatus(shared=exist is not None, share_id=exist)


@router.post("", response_model=ShareOut)
async def create_share(
    payload: ShareCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """分享专辑/播放列表：必须已有 AI 分析结果，且只能分享自己的内容。"""
    song = await db.get(Song, payload.song_id)
    if song is None or song.user_id != user.id:
        raise HTTPException(status_code=404, detail="歌曲不存在")

    pred = (
        await db.execute(select(AiPrediction).where(AiPrediction.song_id == song.id).limit(1))
    ).scalar_one_or_none()
    if pred is None:
        raise HTTPException(status_code=400, detail="请先完成 AI 情绪分析，再进行分享")

    duplicate = (
        await db.execute(
            select(Share).where(Share.user_id == user.id, Share.song_id == song.id).limit(1)
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=400, detail="你已经分享过该内容")

    share = Share(
        user_id=user.id,
        song_id=song.id,
        platform=song.platform or "apple",
        comment=(payload.comment or "").strip() or None,
    )
    db.add(share)
    await db.flush()  # 先拿到 share.id
    # 分享者默认给自己一个赞：分享后点赞数从 1 开始
    db.add(Like(share_id=share.id, user_id=user.id))
    await db.commit()
    await db.refresh(share)
    return _share_to_out(share, song, user, like_count=1, user_liked=True)


async def _count_likes(db: AsyncSession, share_id: int) -> int:
    return (
        await db.execute(select(Like.id).where(Like.share_id == share_id))
    ).scalars().all().__len__()


@router.post("/{share_id}/like", response_model=LikeOut)
async def like_share(
    share_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """点赞分享（联合唯一约束保证不重复，幂等）。"""
    share = await db.get(Share, share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="分享不存在")

    exists = (
        await db.execute(
            select(Like).where(Like.share_id == share_id, Like.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(Like(share_id=share_id, user_id=user.id))
        await db.commit()

    count = await _count_likes(db, share_id)
    return LikeOut(share_id=share_id, liked=True, like_count=count)


@router.delete("/{share_id}/like", response_model=LikeOut)
async def unlike_share(
    share_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消点赞（幂等）。"""
    share = await db.get(Share, share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="分享不存在")

    exists = (
        await db.execute(
            select(Like).where(Like.share_id == share_id, Like.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if exists is not None:
        await db.delete(exists)
        await db.commit()

    count = await _count_likes(db, share_id)
    return LikeOut(share_id=share_id, liked=False, like_count=count)
