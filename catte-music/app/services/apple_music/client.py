"""Apple Music API 客户端封装。

封装搜索、最近播放、打分、创建播放列表等调用。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.apple_music.auth import API_BASE, get_developer_token

logger = logging.getLogger(__name__)


class AppleMusicClient:
    """Apple Music API 异步客户端。"""

    def __init__(self, music_user_token: str | None = None) -> None:
        self._developer_token = get_developer_token()
        self._music_user_token = music_user_token
        self._storefront = "us"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._developer_token}",
            "Content-Type": "application/json",
        }
        if self._music_user_token:
            headers["Music-User-Token"] = self._music_user_token
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{API_BASE}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, headers=self._headers(), **kwargs)
            resp.raise_for_status()
            return resp.json()

    # —— 公开方法 ——

    async def search(self, term: str, limit: int = 25) -> dict:
        """搜索歌曲/专辑/艺术家。"""
        params = {"term": term, "limit": limit, "types": "songs"}
        return await self._request(
            "GET", f"/v1/catalog/{self._storefront}/search", params=params
        )

    async def get_recent_played(self, limit: int = 10) -> dict:
        """获取用户最近播放记录（需 Music User Token）。

        Apple 限制 limit ≤ 10。
        """
        params = {"limit": min(limit, 10)}
        return await self._request(
            "GET", "/v1/me/recent/played", params=params
        )

    async def get_heavy_rotation(self, limit: int = 50) -> dict:
        """获取用户高频播放内容。"""
        params = {"limit": limit}
        return await self._request("GET", "/v1/me/heavy-rotation", params=params)

    async def rate_song(self, song_id: str, rating: int) -> dict:
        """为歌曲打分。rating: 1=喜欢, -1=不喜欢, 0=取消。"""
        return await self._request(
            "PUT",
            f"/v1/me/ratings/songs/{song_id}",
            json={"type": "ratings", "attributes": {"value": rating}},
        )

    async def create_playlist(self, name: str, track_ids: list[str]) -> dict:
        """创建播放列表并添加曲目。"""
        # 1. 创建空播放列表
        playlist = await self._request(
            "POST",
            f"/v1/me/library/playlists",
            json={
                "attributes": {"name": name, "description": "由 Catte Music 创建"},
            },
        )
        playlist_id = playlist["data"][0]["id"]

        # 2. 添加曲目
        if track_ids:
            tracks_data = [
                {"id": tid, "type": "songs"} for tid in track_ids
            ]
            await self._request(
                "POST",
                f"/v1/me/library/playlists/{playlist_id}/tracks",
                json={"data": tracks_data},
            )
        return playlist
