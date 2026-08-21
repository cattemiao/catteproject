"""多标签情绪模型（情绪算法 v2）：OneVsRest HistGBDT ×20 + Platt 校准。

推理接口：
    predict(features) -> {
        "primary": 主情绪名,
        "confidence": 主情绪概率,
        "top_emotions": [{name, color, prob}],   # 概率 > TOP_THRESHOLD
        "probs": {emotion: prob, ...},           # 20 维全向量
        "fuzzy": bool,                            # 主情绪概率 < FUZZY_THRESHOLD
    }

兜底链（由上层 analyze 调用方统一处理）：
    1. 模型文件缺失/加载失败 → 抛 FileNotFoundError，调用方回退模板最近邻；
    2. 某类训练样本 < MIN_CLASS_SUPPORT → 推理时该类概率与模板伪概率混合（0.5/0.5）；
    3. 主情绪概率 < 0.4 → fuzzy=True，前端弱表达。

模型文件 data/models/emotion_model_v2.pkl 结构：
    {
        "model": OneVsRestClassifier(CalibratedClassifierCV(HistGradientBoostingClassifier)),
        "labels": list[str] (20),
        "feature_dim": 65,
        "version": "multilabel-v0.3",
        "per_class_support": {emotion: int},
        "trained_at": iso,
    }
"""
from __future__ import annotations

import joblib
import numpy as np

from app.config import settings
from app.services.ai.feature import template_probs
from app.services.ai.labeling import EMOTION_LABELS
from app.services.ai.seed_emotions import EMOTION_PROFILES

MODEL_PATH = settings.project_root / "data" / "models" / "emotion_model_v2.pkl"
MODEL_VERSION = "multilabel-v0.3"

# 次情绪展示阈值（概率 > 0.35 才算次要情绪）
TOP_THRESHOLD = 0.35
# 主情绪概率低于该值 → 标记「情绪模糊」
FUZZY_THRESHOLD = 0.4
# 训练样本少于该值的类 → 推理时与模板伪概率混合
MIN_CLASS_SUPPORT = 50
# 混合系数：模型概率 0.5 / 模板伪概率 0.5
MIX_WITH_TEMPLATE = 0.5

EMOTION_COLORS = {name: color for name, color, _ in EMOTION_PROFILES}


def is_model_available() -> bool:
    return MODEL_PATH.exists()


def get_model() -> dict:
    """懒加载模型（单例）。"""
    global _model
    if _model is None:
        if not is_model_available():
            raise FileNotFoundError(
                f"模型文件不存在: {MODEL_PATH}，请先运行 training_v2.py 训练模型"
            )
        _model = joblib.load(MODEL_PATH)
    return _model


_model: dict | None = None


def _to_vector(probs: dict[str, float]) -> np.ndarray:
    """{emotion: prob} → 按 EMOTION_LABELS 顺序的 20 维向量。"""
    return np.array([probs.get(name, 0.0) for name in EMOTION_LABELS], dtype=float)


def template_blend(
    model_probs: dict[str, float], features: np.ndarray, per_class_support: dict[str, int]
) -> dict[str, float]:
    """类样本不足 → 该类概率与模板伪概率混合。"""
    if not per_class_support:
        return model_probs
    low_classes = {
        name for name, n in per_class_support.items()
        if n < MIN_CLASS_SUPPORT
    }
    if not low_classes:
        return model_probs
    tmpl = template_probs(features)
    blended = dict(model_probs)
    for name in low_classes:
        blended[name] = (1 - MIX_WITH_TEMPLATE) * model_probs.get(name, 0.0) + MIX_WITH_TEMPLATE * tmpl.get(name, 0.0)
    return blended


def predict_proba(features: np.ndarray) -> dict[str, float]:
    """20 维情绪概率分布 {emotion: prob}（类样本不足时混合模板）。"""
    data = get_model()
    if features.shape[0] != data.get("feature_dim", 65):
        raise ValueError(
            f"特征维度不符: 期望 {data.get('feature_dim')}，实际 {features.shape[0]}"
        )
    estimators = data["model"]  # {emotion: CalibratedClassifierCV | None}
    constants = data.get("class_constants", {})
    x = features.reshape(1, -1)
    probs: dict[str, float] = {}
    for name in data["labels"]:
        clf = estimators.get(name)
        if clf is None:
            probs[name] = constants.get(name, 0.0)
        else:
            p = clf.predict_proba(x)[0]
            probs[name] = float(p[1] if p.shape[0] > 1 else p[0])
    return template_blend(probs, features, data.get("per_class_support", {}))


def predict(features: np.ndarray) -> dict:
    """多标签推理 → (主情绪, top-N, 20 维概率)。"""
    probs = predict_proba(features)

    primary = max(probs, key=probs.get)
    confidence = probs[primary]
    fuzzy = confidence < FUZZY_THRESHOLD

    ranked = sorted(probs.items(), key=lambda x: -x[1])
    top_emotions = [
        {"name": name, "color": EMOTION_COLORS.get(name, "#a855f7"), "prob": round(prob, 4)}
        for name, prob in ranked
        if prob >= TOP_THRESHOLD
    ]
    if not top_emotions:
        # 无情绪超过展示阈值：弱表达 top-3（含主情绪），前端据此弱展示而非空
        top_emotions = [
            {"name": name, "color": EMOTION_COLORS.get(name, "#a855f7"), "prob": round(prob, 4)}
            for name, prob in ranked[:3]
        ]

    return {
        "primary": primary,
        "confidence": round(confidence, 4),
        "top_emotions": top_emotions,
        "probs": {name: round(p, 4) for name, p in probs.items()},
        "fuzzy": fuzzy,
    }


def probs_vector(probs: dict[str, float]) -> np.ndarray:
    """{emotion: prob} → 20 维 numpy 向量（推荐相似度用）。"""
    return _to_vector(probs)


def reset_model_cache() -> None:
    """重置模型单例（测试用）。"""
    global _model
    _model = None
