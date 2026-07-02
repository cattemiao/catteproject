"""Apple Music 评分/标签数据爬虫。

示例实现骨架：分页请求 + BeautifulSoup 解析 + 去重入库。
实际 Apple Music 页面结构需根据抓包结果调整选择器。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from app.config import settings
from app.services.crawler.anti_crawl import make_session, random_delay

if TYPE_CHECKING:
    import requests

logger = logging.getLogger(__name__)

DATA_RAW_DIR = settings.project_root / "data" / "raw" / "ratings"


@dataclass
class RatingRecord:
    title: str
    artist: str
    album: str | None
    rating: float | None
    tags: list[str]


def _parse_page(html: str) -> list[RatingRecord]:
    """从一页 HTML 解析评分记录。选择器需根据实际页面结构调整。"""
    soup = BeautifulSoup(html, "lxml")
    records: list[RatingRecord] = []

    for item in soup.select(".song-item"):  # 占位选择器
        title = (item.select_one(".title") or {}).get_text(strip=True)  # type: ignore[union-attr]
        artist = (item.select_one(".artist") or {}).get_text(strip=True)  # type: ignore[union-attr]
        album_el = item.select_one(".album")
        rating_el = item.select_one(".rating")
        tag_els = item.select(".tag")

        records.append(
            RatingRecord(
                title=title,
                artist=artist,
                album=album_el.get_text(strip=True) if album_el else None,
                rating=float(rating_el.get_text(strip=True)) if rating_el else None,
                tags=[t.get_text(strip=True) for t in tag_els],
            )
        )
    return records


def crawl_ratings(
    base_url: str,
    max_pages: int = 100,
    start_page: int = 1,
) -> list[RatingRecord]:
    """抓取评分数据，支持断点续爬（从 start_page 开始）。"""
    session = make_session()
    all_records: list[RatingRecord] = []
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    for page in range(start_page, start_page + max_pages):
        url = f"{base_url}?page={page}"
        logger.info("爬取第 %d 页: %s", page, url)
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("第 %d 页请求失败: %s", page, exc)
            break

        records = _parse_page(resp.text)
        if not records:
            logger.info("第 %d 页无数据，结束爬取", page)
            break

        all_records.extend(records)

        # 每页存盘，支持断点
        out = DATA_RAW_DIR / f"page_{page:04d}.json"
        out.write_text(
            json.dumps([r.__dict__ for r in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 记录断点
        (DATA_RAW_DIR / "last_page.txt").write_text(str(page), encoding="utf-8")

        random_delay(settings.crawl_delay_min, settings.crawl_delay_max)

    logger.info("共爬取 %d 条评分记录", len(all_records))
    return all_records


def get_last_page() -> int:
    """读取上次爬取到的页码，用于断点续爬。"""
    f = DATA_RAW_DIR / "last_page.txt"
    if f.exists():
        return int(f.read_text().strip()) + 1
    return 1
