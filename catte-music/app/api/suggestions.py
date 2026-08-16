"""意见投稿路由：所有人可见，登录后可投稿。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.suggestion import Suggestion
from app.models.user import User

router = APIRouter(prefix="/api/suggestions", tags=["意见投稿"])


class SuggestionCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class SuggestionOut(BaseModel):
    id: int
    username: str
    content: str
    created_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SuggestionOut])
async def list_suggestions(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取所有用户的意见投稿（所有人可见，无需登录）。"""
    result = await db.execute(
        select(Suggestion).order_by(Suggestion.id.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return [
        SuggestionOut(
            id=r.id,
            username=r.username,
            content=r.content,
            created_at=r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        )
        for r in rows
    ]


@router.post("", response_model=SuggestionOut, status_code=201)
async def create_suggestion(
    payload: SuggestionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交意见投稿（需登录）。"""
    sug = Suggestion(
        user_id=user.id,
        username=user.username,
        content=payload.content.strip(),
    )
    db.add(sug)
    await db.flush()
    return SuggestionOut(
        id=sug.id,
        username=sug.username,
        content=sug.content,
        created_at=sug.created_at.strftime("%Y-%m-%d %H:%M") if sug.created_at else "",
    )
