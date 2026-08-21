"""多标签情绪模型训练与评估（情绪算法 v2，CPU）。

数据目录（--dataset，默认 data/raw/emotion_dataset_v2/）：
    features.npy    # (n, 65) 特征矩阵
    labels.json     # [{key, labels, confidence, sources}]
    gold.json       # 可选金标准 [{key, labels, primary}]（权重 ×5）

流程：
    加载 → 组装 (X, Y, sample_weight) → 分层 5-fold 评估
    → 模板最近邻基线对比（伪概率 + 0.35 阈值转多标签）
    → 全量训练（OneVsRest HistGBDT + Platt 校准）→ joblib 导出

指标：宏 F1、每类 F1、Hamming loss、子集准确率；每类训练样本数（per_class_support）。

用法：
    python -m app.services.ai.training_v2 --dataset data/raw/emotion_dataset_v2
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    hamming_loss,
)
from sklearn.model_selection import StratifiedKFold

from app.services.ai.feature import FEATURE_DIM, template_probs
from app.services.ai.labeling import EMOTION_LABELS, load_gold
from app.services.ai.model import MIN_CLASS_SUPPORT, MODEL_VERSION, template_blend

logger = logging.getLogger(__name__)

# 多标签预测阈值（评估用）
PREDICT_THRESHOLD = 0.35


def _load_dataset(dataset_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """加载 features.npy + labels.json（+ gold.json）→ (X, Y, sample_weight)。"""
    features = np.load(dataset_dir / "features.npy")
    samples = json.loads((dataset_dir / "labels.json").read_text(encoding="utf-8"))

    gold = load_gold(dataset_dir / "gold.json")
    gold_map = {g["key"]: g for g in gold}

    label_index = {name: i for i, name in enumerate(EMOTION_LABELS)}
    x_list, y_list, w_list = [], [], []
    for i, s in enumerate(samples):
        if i >= len(features):
            break
        x_list.append(features[i])
        y = [0] * len(EMOTION_LABELS)
        for e in s["labels"]:
            y[label_index[e]] = 1
        y_list.append(y)
        gold_entry = gold_map.get(s["key"])
        w_list.append(gold_entry.get("weight", 1.0) if gold_entry else s.get("weight", 1.0))

    if not x_list:
        raise ValueError(f"数据目录无有效样本: {dataset_dir}")

    logger.info(
        "数据集加载: %d 样本, 特征 %d 维, 金标准覆盖 %d 条",
        len(x_list), len(x_list[0]), len(gold),
    )
    return (
        np.array(x_list, dtype=float),
        np.array(y_list, dtype=int),
        np.array(w_list, dtype=float),
    )


def _eval_predictions(y_true: np.ndarray, proba: np.ndarray) -> dict:
    """多指标评估：0.35 阈值多标签 + top-2 表达 + 主情绪 Top-1 命中率。"""
    y_pred = (proba >= PREDICT_THRESHOLD).astype(int)
    # top-2 多标签（对应推理弱表达路径：概率前 2 作为预测集）
    y_pred_top2 = np.zeros_like(y_true)
    for r in range(proba.shape[0]):
        top = np.argsort(proba[r])[::-1][:2]
        y_pred_top2[r, top] = 1
    per_class = f1_score(y_true, y_pred, average=None, zero_division=0)
    primary_true = y_true.argmax(axis=1)
    primary_pred = proba.argmax(axis=1)
    return {
        "primary_acc": round(float((primary_true == primary_pred).mean()), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "macro_f1_top2": round(float(f1_score(y_true, y_pred_top2, average="macro", zero_division=0)), 4),
        "hamming_loss": round(float(hamming_loss(y_true, y_pred)), 4),
        "subset_accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "per_class_f1": {
            name: round(float(per_class[i]), 4) for i, name in enumerate(EMOTION_LABELS)
        },
    }


def _template_baseline_eval(X: np.ndarray, Y: np.ndarray) -> dict:
    """模板最近邻基线：template_probs 概率矩阵，同指标评估（含主情绪 Top-1）。"""
    proba = np.zeros((X.shape[0], len(EMOTION_LABELS)))
    for i, feat in enumerate(X):
        probs = template_probs(feat)
        proba[i] = [probs.get(name, 0.0) for name in EMOTION_LABELS]
    return _eval_predictions(Y, proba)


def _fit_binary(
    X: np.ndarray, y: np.ndarray, weights: np.ndarray,
) -> tuple[CalibratedClassifierCV | None, float]:
    """训练单个情绪类的二分类器（HistGBDT + Platt 校准）。

    Returns:
        (classifier | None, 常量概率) — 单类或正/负样本不足以支撑
        交叉验证时返回 None + 该类占比（预测恒定为该值，推理时与模板混合兜底）。
    """
    unique = np.unique(y)
    if len(unique) == 1:
        return None, float(unique[0])
    pos = int(y.sum())
    neg = int((y == 0).sum())
    # 正负样本任一不足以支撑校准 CV → 退化为常量概率，避免 StratifiedKFold 崩溃
    if pos < 2 or neg < 2:
        return None, float(y.mean())
    base = HistGradientBoostingClassifier(
        max_iter=100, learning_rate=0.1, random_state=42,
    )
    clf = CalibratedClassifierCV(
        estimator=base,
        method="sigmoid",
        cv=min(3, max(2, pos // 4), pos, neg),  # 折数受限于最少类样本数
        ensemble=True,
    )
    clf.fit(X, y, sample_weight=weights)
    return clf, float(y.mean())


def _fit_estimators(
    X: np.ndarray, Y: np.ndarray, weights: np.ndarray,
) -> tuple[dict[str, CalibratedClassifierCV | None], dict[str, float]]:
    """训练 20 个二分类器（OneVsRest）。"""
    estimators: dict[str, CalibratedClassifierCV | None] = {}
    constants: dict[str, float] = {}
    for i, name in enumerate(EMOTION_LABELS):
        clf, const = _fit_binary(X, Y[:, i], weights)
        estimators[name] = clf
        constants[name] = const
    return estimators, constants


def _predict_proba(
    X: np.ndarray,
    estimators: dict[str, CalibratedClassifierCV | None],
    constants: dict[str, float],
) -> np.ndarray:
    """(n, 20) 概率矩阵。"""
    n = X.shape[0]
    proba = np.zeros((n, len(EMOTION_LABELS)))
    for i, name in enumerate(EMOTION_LABELS):
        clf = estimators.get(name)
        if clf is None:
            proba[:, i] = constants.get(name, 0.0)
        else:
            p = clf.predict_proba(X)
            proba[:, i] = p[:, 1] if p.shape[1] > 1 else p[:, 0]
    return proba


def evaluate(X: np.ndarray, Y: np.ndarray, weights: np.ndarray) -> dict:
    """分层 5-fold 评估（基于主情绪分层近似），并返回模板基线对比。"""
    primary_idx = Y.argmax(axis=1)
    n_folds = min(5, max(2, np.bincount(primary_idx).min()))
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

    y_true_all, proba_all = [], []
    for train_idx, test_idx in cv.split(X, primary_idx):
        estimators, constants = _fit_estimators(X[train_idx], Y[train_idx], weights[train_idx])
        support = {
            name: int(Y[train_idx][:, i].sum()) for i, name in enumerate(EMOTION_LABELS)
        }
        proba = _predict_proba(X[test_idx], estimators, constants)
        # 与推理路径一致：类样本不足时混合模板伪概率
        for r in range(proba.shape[0]):
            row = {name: float(proba[r, i]) for i, name in enumerate(EMOTION_LABELS)}
            row = template_blend(row, X[test_idx][r], support)
            for i, name in enumerate(EMOTION_LABELS):
                proba[r, i] = row[name]
        y_true_all.append(Y[test_idx])
        proba_all.append(proba)

    y_true = np.vstack(y_true_all)
    proba = np.vstack(proba_all)
    model_metrics = _eval_predictions(y_true, proba)
    baseline_metrics = _template_baseline_eval(X, Y)
    return {"model": model_metrics, "template_baseline": baseline_metrics}


def train(dataset_dir: Path, output_path: Path) -> dict:
    """全量训练 + 导出。"""
    X, Y, weights = _load_dataset(dataset_dir)
    if X.shape[1] != FEATURE_DIM:
        logger.warning("特征维度 %d ≠ %d（模型预期），请确认数据来源", X.shape[1], FEATURE_DIM)

    per_class_support = {name: int(Y[:, i].sum()) for i, name in enumerate(EMOTION_LABELS)}
    low = [n for n, c in per_class_support.items() if c < MIN_CLASS_SUPPORT]
    if low:
        logger.warning("样本不足的类（推理时与模板混合）: %s", ", ".join(low))

    estimators, constants = _fit_estimators(X, Y, weights)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": estimators,
        "labels": EMOTION_LABELS,
        "feature_dim": int(X.shape[1]),
        "version": MODEL_VERSION,
        "per_class_support": per_class_support,
        "class_constants": constants,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(artifact, output_path)
    logger.info("模型已导出: %s", output_path)
    return per_class_support


def main() -> None:
    parser = argparse.ArgumentParser(description="多标签情绪模型训练与评估")
    parser.add_argument("--dataset", type=Path, default=Path("data/raw/emotion_dataset_v2"))
    parser.add_argument("--output", type=Path, default=Path("data/models/emotion_model_v2.pkl"))
    parser.add_argument("--skip-eval", action="store_true", help="跳过 5-fold 评估，直接全量训练")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    X, Y, weights = _load_dataset(args.dataset)

    if not args.skip_eval:
        report = evaluate(X, Y, weights)
        logger.info("── 模型（多标签 HistGBDT ×20）──")
        for k, v in report["model"].items():
            if k != "per_class_f1":
                logger.info("  %s = %s", k, v)
        logger.info("── 模板基线（最近邻伪概率）──")
        for k, v in report["template_baseline"].items():
            if k != "per_class_f1":
                logger.info("  %s = %s", k, v)
        low_classes = [n for n, f in report["model"]["per_class_f1"].items() if f < 0.5]
        logger.info("F1 < 0.5 的类: %d/20 (%s)", len(low_classes), ", ".join(low_classes))

    train(args.dataset, args.output)


if __name__ == "__main__":
    main()
