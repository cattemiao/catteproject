"""认证相关 Pydantic 模型。"""
from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False


class UserOut(BaseModel):
    id: int
    username: str
    has_apple_music: bool = False
    has_netease: bool = False

    model_config = {"from_attributes": True}
