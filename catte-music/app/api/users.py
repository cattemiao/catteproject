"""用户路由：查看指定用户的歌单、当前用户的统计与音乐风格画像。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.songs import _song_to_out
from app.database import get_db
from app.models.prediction import AiPrediction
from app.models.share import Share
from app.models.song import Song
from app.models.user import Emotion, User
from app.schemas.song import SongListOut

router = APIRouter(prefix="/api/users", tags=["用户"])

# 七维声学指标（对应 ai_predictions 表的列）
_DIMENSION_COLS = (
    "loudness",
    "high_freq",
    "rhythm",
    "soundstage",
    "layering",
    "soothing",
    "prosody",
)


def _extract_genres(platform: str, raw_meta) -> list[str]:
    """从歌曲 raw_meta 中提取流派列表。"""
    if not isinstance(raw_meta, dict):
        return []
    if platform == "apple":
        attrs = raw_meta.get("attributes")
        if isinstance(attrs, dict):
            raw_meta = attrs
        genres = raw_meta.get("genreNames") or raw_meta.get("genres") or []
        return [str(g) for g in genres] if isinstance(genres, list) else []
    enriched = raw_meta.get("_enriched")
    if isinstance(enriched, dict) and isinstance(enriched.get("genres"), list):
        return [str(g) for g in enriched["genres"]]
    return []


@router.get("/me/stats")
async def me_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """当前用户的音乐库统计与整体音乐风格画像。"""
    # 1) 平台歌曲/专辑统计（专辑含歌单）
    rows = (
        await db.execute(
            select(Song.platform, Song.type, func.count())
            .where(Song.user_id == user.id)
            .group_by(Song.platform, Song.type)
        )
    ).all()
    albums = {"apple": 0, "netease": 0}
    singles = {"apple": 0, "netease": 0}
    for platform, stype, count in rows:
        if stype == "song":
            singles[platform] += count
        else:  # albums / playlists
            albums[platform] += count

    # 2) 分享数 / AI 分析数
    shares = (
        await db.execute(
            select(func.count()).select_from(Share).where(Share.user_id == user.id)
        )
    ).scalar() or 0
    analyses = (
        await db.execute(
            select(func.count())
            .select_from(AiPrediction)
            .join(Song, Song.id == AiPrediction.song_id)
            .where(Song.user_id == user.id)
        )
    ).scalar() or 0

    # 3) 情绪分布（每首歌只取最新一条预测）
    pred_rows = (
        await db.execute(
            select(AiPrediction.song_id, Emotion.name, Emotion.color)
            .join(Song, Song.id == AiPrediction.song_id)
            .join(Emotion, Emotion.id == AiPrediction.emotion_id)
            .where(Song.user_id == user.id)
            .order_by(AiPrediction.id.desc())
        )
    ).all()
    seen_songs: set[int] = set()
    emotion_count: dict[str, int] = {}
    emotion_color: dict[str, str] = {}
    for song_id, name, color in pred_rows:
        if song_id in seen_songs:
            continue
        seen_songs.add(song_id)
        emotion_count[name] = emotion_count.get(name, 0) + 1
        emotion_color.setdefault(name, color or "#a855f7")
    emotion_distribution = [
        {"name": name, "color": emotion_color[name], "count": count}
        for name, count in sorted(emotion_count.items(), key=lambda x: -x[1])
    ]
    top_emotion = emotion_distribution[0]["name"] if emotion_distribution else None

    # 4) 七维平均画像（每首歌取最新预测去重）
    dim_rows = (
        await db.execute(
            select(
                AiPrediction.song_id,
                *[getattr(AiPrediction, c) for c in _DIMENSION_COLS],
            )
            .join(Song, Song.id == AiPrediction.song_id)
            .where(Song.user_id == user.id)
            .order_by(AiPrediction.id.desc())
        )
    ).all()
    seen_dim: set[int] = set()
    vecs: list[list[float]] = []
    for row in dim_rows:
        if row.song_id in seen_dim:
            continue
        seen_dim.add(row.song_id)
        vals = [float(v) for v in row[1:]]
        if all(v is not None for v in vals):
            vecs.append(vals)
    if vecs:
        emotion_dimensions = [
            {
                "dimension": col,
                "avg": round(sum(v[i] for v in vecs) / len(vecs), 1),
                "count": len(vecs),
            }
            for i, col in enumerate(_DIMENSION_COLS)
        ]
    else:
        emotion_dimensions = [
            {"dimension": col, "avg": 0.0, "count": 0} for col in _DIMENSION_COLS
        ]

    # 5) 整体流派偏好（Top3）
    song_meta = (
        await db.execute(
            select(Song.platform, Song.raw_meta).where(Song.user_id == user.id)
        )
    ).all()
    genre_count: dict[str, int] = {}
    for platform, raw_meta in song_meta:
        for genre in _extract_genres(platform, raw_meta):
            genre_count[genre] = genre_count.get(genre, 0) + 1
    top_genres = sorted(genre_count.items(), key=lambda x: -x[1])[:3]

    return {
        "apple_songs": singles["apple"],
        "apple_albums": albums["apple"],
        "netease_songs": singles["netease"],
        "netease_albums": albums["netease"],
        "shares": shares,
        "analyses": analyses,
        "emotion_distribution": emotion_distribution,
        "emotion_dimensions": emotion_dimensions,
        "top_emotion": top_emotion,
        "top_genres": top_genres,
    }


@router.get("/{user_id}/songs", response_model=SongListOut)
async def user_songs(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """返回指定用户（分享者）的歌单：其同步/分析的专辑与播放列表。"""
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    result = await db.execute(
        select(Song).where(Song.user_id == user_id).order_by(Song.id.desc())
    )
    items = [_song_to_out(s) for s in result.scalars().all()]
    return SongListOut(total=len(items), items=items)
