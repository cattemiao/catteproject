"""站点统计路由：前端页面访问上报（无需登录）。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pageview import PageView

router = APIRouter(prefix="/api/stats", tags=["站点统计"])


class PageViewIn(BaseModel):
    path: str = "/"


@router.post("/pageview")
async def record_pageview(payload: PageViewIn, db: AsyncSession = Depends(get_db)):
    """前端每次路由切换上报一次访问。"""
    db.add(PageView(path=payload.path[:256] or "/"))
    await db.flush()
    return {"ok": True}
