"""FastAPI 应用入口：挂载路由、启动建表、CORS。"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, analyze, apple_music, auth, emotions, netease, recommend, shares, songs, stats, suggestions, users
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动建表
    await init_db()
    # 初始化情绪模板数据
    from app.services.ai.seed_emotions import seed

    await seed()
    # 后台自动 AI 分析任务：低负载时扫描未分析的专辑/歌单生成情绪数据
    from app.services.ai.auto_analyze import auto_analyze_loop

    analyzer_task = asyncio.create_task(auto_analyze_loop())
    try:
        yield
    finally:
        analyzer_task.cancel()
        try:
            await analyzer_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Catte Music API",
    description="AI 音乐情绪可视化与探索平台后端",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.middleware("http")
async def track_active_users(request: Request, call_next):
    """记录最近活跃的登录用户（供后台低负载自动 AI 分析判断）。"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        from app.services.active_users import active_users
        from app.utils.security import decode_access_token

        username = decode_access_token(auth[7:])
        if username:
            active_users.touch(username)
    return await call_next(request)


# 挂载路由
app.include_router(auth.router)
app.include_router(songs.router)
app.include_router(analyze.router)
app.include_router(emotions.router)
app.include_router(recommend.router)
app.include_router(shares.router)
app.include_router(users.router)
app.include_router(apple_music.router)
app.include_router(netease.router)
app.include_router(suggestions.router)
app.include_router(stats.router)
app.include_router(admin.router)
