"""FastAPI 依赖：JWT 鉴权、获取当前用户与数据库会话。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 解析当前用户。"""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = decode_access_token(token)
    if username is None:
        raise credentials_exc

    # 管理员为虚拟账号：密码来自环境变量，不落库
    if settings.admin_password and username == settings.admin_username:
        return User(id=0, username=username)

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """仅管理员可用的依赖：未配置 admin 密码或非 admin 用户直接 403。"""
    if not settings.admin_password or user.username != settings.admin_username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user
