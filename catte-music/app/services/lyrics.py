"""歌词服务：从 Apple Music API 获取歌词并分段。"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.services.apple_music.auth import API_BASE, get_developer_token

logger = logging.getLogger(__name__)
STORE = "us"


async def fetch_lyrics(apple_music_id: str) -> dict[str, Any]:
    """从 Apple Music catalog 获取歌曲歌词。

    返回:
        {
            "lyrics": "原始歌词文本（按行分隔）",
            "segments": ["段落1", "段落2", ...],
            "source": "apple_music_catalog"
        }
    如果不可用返回 None。
    """
    dev_token = get_developer_token()
    headers = {"Authorization": f"Bearer {dev_token}"}

    async with httpx.AsyncClient(timeout=15.0) as cli:
        # 尝试获取歌曲信息（含歌词）
        try:
            resp = await cli.get(
                f"{API_BASE}/v1/catalog/{STORE}/songs/{apple_music_id}",
                params={"include": "lyrics"},
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return {"lyrics": "", "segments": [], "source": "unavailable"}

    data = resp.json()
    song_data = data.get("data", [{}])[0] if isinstance(data.get("data"), list) else data.get("data", {})
    
    # 检查是否有歌词
    if not song_data:
        return {"lyrics": "", "segments": [], "source": "unavailable"}

    # 尝试从 relationships 获取歌词
    lyrics_text = ""
    relationships = song_data.get("relationships", {})
    lyrics_data = relationships.get("lyrics", {}).get("data", [])
    
    if lyrics_data:
        for lyric_item in lyrics_data:
            attrs = lyric_item.get("attributes", {})
            lyrics_text = attrs.get("ttml", "") or attrs.get("plainLyrics", "")
            if lyrics_text:
                break

    if not lyrics_text:
        return {"lyrics": "", "segments": [], "source": "unavailable"}

    # 清理 TTML 标签，提取纯文本
    clean_lyrics = _clean_ttml(lyrics_text)
    segments = _split_into_segments(clean_lyrics)

    return {
        "lyrics": clean_lyrics,
        "segments": segments,
        "source": "apple_music_catalog",
    }


def _clean_ttml(ttml_text: str) -> str:
    """清理 TTML/XML 标签，提取纯歌词文本。"""
    # 移除 XML 标签
    text = re.sub(r"<[^>]+>", "", ttml_text)
    # 解码 XML 实体
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    return text


def _split_into_segments(lyrics_text: str) -> list[str]:
    """将歌词文本按空行分割为段落。"""
    if not lyrics_text:
        return []
    # 按空行分割
    raw_segments = re.split(r"\n\s*\n", lyrics_text.strip())
    # 过滤纯空白段 + 去除首尾空白
    segments = [s.strip() for s in raw_segments if s.strip()]
    return segments


def generate_image_prompt(lyric_segment: str, emotion_hint: str = "") -> dict[str, str]:
    """为歌词段落生成 AI 图片提示词。

    返回适合 Stable Diffusion / Replicate 的 prompt。
    AI 图片生成需要外部 API key，此处提供 prompt 生成接口。
    """
    # 基础风格
    base_style = "ethereal dreamlike atmosphere, cinematic lighting, 8k, trending on artstation"

    # 情绪色板映射
    emotion_palettes: dict[str, str] = {
        "甜蜜": "soft pink and gold tones, warm sunlight, cherry blossoms",
        "浪漫": "rose gold sunset, candlelit glow, velvet textures",
        "治愈": "soft teal and cream, morning light, gentle waves",
        "悲伤": "deep blue and silver, rain streaked window, fading light",
        "孤独": "misty grey, single silhouette, empty streets",
        "深情": "deep purple twilight, starry sky, intimate warmth",
        "欢快": "vibrant yellow and orange, confetti, bright daylight",
        "愤怒": "crimson storm, shattered glass, lightning",
        "宁静": "sage green and ivory, zen garden, still water reflection",
        "热血": "flame red and gold, epic battle scene, dramatic clouds",
        "忧郁": "faded indigo, autumn leaves, solitary figure",
        "激昂": "electric blue and white, stadium lights, triumphant",
        "松弛": "warm beige and sage, hammock by the beach, lazy afternoon",
        "梦幻": "iridescent purple and cyan, floating islands, aurora borealis",
        "震撼": "golden burst, cathedral light rays, cosmic scale",
        "舒缓": "pastel lavender, soft clouds, gentle breeze through wheat field",
        "自由": "turquoise ocean, soaring eagle, endless horizon",
        "空灵": "transparent crystal, ethereal mist, weightless in zero gravity",
        "狂野": "neon orange and black, wildfire, untamed wilderness",
        "迷幻": "psychedelic swirl, kaleidoscope patterns, melting colors",
    }

    palette = emotion_palettes.get(emotion_hint, "cinematic blue and purple tones")

    prompt = f"{lyric_segment[:80]}, {palette}, {base_style}"

    return {
        "prompt": prompt,
        "negative_prompt": "blurry, low quality, ugly, distorted, watermark, text",
        "segment": lyric_segment,
    }