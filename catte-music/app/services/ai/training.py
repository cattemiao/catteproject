"""模型训练与导出。

用法:
    python -m app.services.ai.training --data-dir data/audio_samples --output data/models/emotion_model.pkl
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

from app.services.ai.classifier import EMOTION_LABELS
from app.services.ai.feature import extract_features

logger = logging.getLogger(__name__)


def build_training_data(data_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """从目录构建训练集。

    目录结构要求:
        data_dir/
            治愈/
                song1.mp3
                song2.mp3
            悲伤/
                song3.mp3
            ...

    Returns:
        (X 特征矩阵, y 标签索引)
    """
    x_list: list[np.ndarray] = []
    y_list: list[int] = []

    for emotion_dir in sorted(data_dir.iterdir()):
        if not emotion_dir.is_dir():
            continue
        emotion_name = emotion_dir.name
        if emotion_name not in EMOTION_LABELS:
            logger.warning("跳过未知情绪标签: %s", emotion_name)
            continue

        label_idx = EMOTION_LABELS.index(emotion_name)
        for audio_file in emotion_dir.glob("*.mp3"):
            try:
                features = extract_features(audio_file)
                x_list.append(features)
                y_list.append(label_idx)
                logger.info("提取 %s [%s]", audio_file.name, emotion_name)
            except Exception as exc:
                logger.error("提取失败 %s: %s", audio_file, exc)

    return np.array(x_list), np.array(y_list)


def train(
    data_dir: Path,
    output_path: Path,
) -> RandomForestClassifier:
    """训练 RandomForest 情绪分类器并导出。"""
    logger.info("构建训练集: %s", data_dir)
    X, y = build_training_data(data_dir)
    if len(X) == 0:
        raise ValueError("训练集为空，请检查数据目录结构")

    logger.info("训练集大小: %d 样本, %d 维特征", len(X), X.shape[1])

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
    )

    # 5 折交叉验证
    scores = cross_val_score(model, X, y, cv=min(5, len(X)), scoring="f1_macro")
    logger.info("交叉验证 f1-macro: %.4f ± %.4f", scores.mean(), scores.std())

    # 全量训练
    model.fit(X, y)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    logger.info("模型已导出: %s", output_path)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="训练情绪分类模型")
    parser.add_argument("--data-dir", type=Path, default=Path("data/audio_samples"))
    parser.add_argument("--output", type=Path, default=Path("data/models/emotion_model.pkl"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    train(args.data_dir, args.output)


if __name__ == "__main__":
    main()
