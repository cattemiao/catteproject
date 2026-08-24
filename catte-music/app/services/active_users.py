"""活跃用户内存追踪。

通过请求中间件记录最近有 API 请求的登录用户（含 admin），
供后台自动 AI 分析判断"当前系统负载"：活跃用户数低于阈值时触发。
单进程内存实现即可满足需求（uvicorn 单进程部署）。
"""
from __future__ import annotations

import threading
import time

# 多久内有过请求算"活跃用户"（秒）
ACTIVE_WINDOW_SECONDS = 300


class ActiveUserTracker:
    def __init__(self, window_seconds: int = ACTIVE_WINDOW_SECONDS):
        self._window = window_seconds
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def touch(self, username: str) -> None:
        """记录某用户的最近活跃时间。"""
        with self._lock:
            self._last_seen[username] = time.monotonic()

    def active_count(self) -> int:
        """返回当前活跃用户数（同时清理超时记录）。"""
        cutoff = time.monotonic() - self._window
        with self._lock:
            self._last_seen = {u: t for u, t in self._last_seen.items() if t > cutoff}
            return len(self._last_seen)


# 全局单例
active_users = ActiveUserTracker()
