"""FastAPI 应用入口：挂载路由、启动建表、CORS。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, analyze, apple_music, auth, emotions, netease, recommend, songs, stats, suggestions
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动建表
    await init_db()
    # 初始化情绪模板数据
    from app.services.ai.seed_emotions import seed

    await seed()
    yield


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


# 挂载路由
app.include_router(auth.router)
app.include_router(songs.router)
app.include_router(analyze.router)
app.include_router(emotions.router)
app.include_router(recommend.router)
app.include_router(apple_music.router)
app.include_router(netease.router)
app.include_router(suggestions.router)
app.include_router(stats.router)
app.include_router(admin.router)
