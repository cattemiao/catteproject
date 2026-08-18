"""认证路由：注册、登录、Apple Music 授权。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, UserLogin, UserOut, UserRegister
from app.services.apple_music.auth import get_developer_token
from app.utils.security import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    if data.username == settings.admin_username:
        raise HTTPException(status_code=400, detail=f"「{settings.admin_username}」为保留账号，不可注册")
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    return UserOut(id=user.id, username=user.username, has_apple_music=False, has_netease=False)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    # 管理员：密码由 .env 的 ADMIN_PASSWORD 设置，不落库
    if data.username == settings.admin_username:
        if not settings.admin_password or data.password != settings.admin_password:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token = create_access_token(data.username)
        return Token(access_token=token, is_admin=True)

    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user.username)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(
        id=user.id,
        username=user.username,
        has_apple_music=bool(user.apple_music_token),
        has_netease=bool(user.netease_cookie),
    )


@router.get("/apple-music/config")
async def apple_music_config():
    """返回前端 MusicKit 初始化所需的 Developer Token。"""
    return {
        "developer_token": get_developer_token(),
        "app_name": "Catte Music",
        "build": "0.1",
    }


@router.post("/apple-music/callback")
async def apple_music_callback(
    payload: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """接收前端授权后的 Music User Token 并存储。"""
    music_user_token = payload.get("music_user_token")
    if not music_user_token:
        raise HTTPException(status_code=400, detail="缺少 music_user_token")

    user.apple_music_token = music_user_token
    await db.flush()
    return {"status": "ok"}
