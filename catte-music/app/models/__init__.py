"""数据库模型汇总导入，确保所有模型注册到 Base.metadata。"""
from app.models.pageview import PageView
from app.models.prediction import AiPrediction
from app.models.share import Like, Share
from app.models.song import CrawlRecord, Song, SongEmotion, SongTag, Tag
from app.models.suggestion import Suggestion
from app.models.user import Emotion, EmotionDimension, User, UserFavorite

__all__ = [
    "User",
    "UserFavorite",
    "Song",
    "CrawlRecord",
    "Emotion",
    "EmotionDimension",
    "SongEmotion",
    "Tag",
    "SongTag",
    "AiPrediction",
    "Suggestion",
    "PageView",
    "Share",
    "Like",
]
