"""情绪分类器：加载训练好的模型进行推理。"""
from __future__ import annotations

import joblib
import numpy as np

from app.config import settings

MODEL_PATH = settings.project_root / "data" / "models" / "emotion_model.pkl"

# 情绪标签体系（15 种）
EMOTION_LABELS = [
    "甜蜜", "浪漫", "治愈", "孤独", "悲伤",
    "深情", "欢快", "愤怒", "宁静", "热血",
    "忧郁", "激昂", "松弛", "梦幻", "震撼",
]

# 情绪主色调映射
EMOTION_COLORS = {
    "甜蜜": "#ec4899",
    "浪漫": "#f472b6",
    "治愈": "#22d3ee",
    "孤独": "#64748b",
    "悲伤": "#3b82f6",
    "深情": "#a855f7",
    "欢快": "#fbbf24",
    "愤怒": "#ef4444",
    "宁静": "#14b8a6",
    "热血": "#f97316",
    "忧郁": "#818cf8",
    "激昂": "#f43f5e",
    "松弛": "#34d399",
    "梦幻": "#c084fc",
    "震撼": "#e879f9",
}

_model = None


def get_model():
    """懒加载模型（单例）。"""
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"模型文件不存在: {MODEL_PATH}，请先运行 training.py 训练模型"
            )
        _model = joblib.load(MODEL_PATH)
    return _model


def predict(features: np.ndarray) -> tuple[str, float]:
    """对特征向量进行情绪预测。

    Args:
        features: extract_features 返回的一维特征向量

    Returns:
        (情绪标签, 置信度) — 置信度为预测概率最大值
    """
    model = get_model()
    features_2d = features.reshape(1, -1)

    label_idx = model.predict(features_2d)[0]
    proba = (
        model.predict_proba(features_2d)[0]
        if hasattr(model, "predict_proba")
        else None
    )

    confidence = float(max(proba)) if proba is not None else 1.0
    label = (
        EMOTION_LABELS[int(label_idx)]
        if isinstance(label_idx, (int, np.integer))
        else str(label_idx)
    )
    return label, confidence


def get_emotion_color(emotion: str) -> str:
    return EMOTION_COLORS.get(emotion, "#a855f7")
