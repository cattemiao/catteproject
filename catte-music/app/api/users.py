"""用户主页路由：查看指定用户的歌单。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.songs import _song_to_out
from app.database import get_db
from app.models.song import Song
from app.models.user import User
from app.schemas.song import SongListOut

router = APIRouter(prefix="/api/users", tags=["用户"])


@router.get("/{user_id}/songs", response_model=SongListOut)
async def user_songs(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """返回指定用户（分享者）的歌单：其同步/分析的专辑与播放列表。"""
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    result = await db.execute(
        select(Song).where(Song.user_id == user_id).order_by(Song.id.desc())
    )
    items = [_song_to_out(s) for s in result.scalars().all()]
    return SongListOut(total=len(items), items=items)
