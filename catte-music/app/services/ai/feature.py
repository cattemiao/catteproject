"""librosa 音频特征提取。

提取节奏(BPM)、响度、频谱质心、过零率、MFCC(13维均值)等声学特征。
"""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np


def extract_features(file_path: str | Path, sr: int = 22050) -> np.ndarray:
    """加载音频并提取固定维度特征向量。

    Returns:
        一维 numpy 数组，结构：
        [tempo, rmse_mean, spectral_centroid_mean, zcr_mean, mfcc_0..mfcc_12]
        共 17 维。
    """
    y, sr = librosa.load(str(file_path), sr=sr, mono=True)

    # 节奏 BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

    # 响度 (RMS 均值)
    rmse = librosa.feature.rms(y=y)

    # 频谱质心均值
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)

    # 过零率均值
    zcr = librosa.feature.zero_crossing_rate(y)

    # MFCC 13 维取均值
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

    features = np.concatenate(
        [
            np.array([float(tempo)]),
            np.array([float(rmse.mean())]),
            np.array([float(spectral_centroid.mean())]),
            np.array([float(zcr.mean())]),
            mfcc.mean(axis=1),  # 13 维
        ]
    )
    return features


def feature_names() -> list[str]:
    """返回特征名列表，与 extract_features 输出维度一一对应。"""
    base = ["tempo", "rmse_mean", "spectral_centroid_mean", "zcr_mean"]
    mfcc_names = [f"mfcc_{i}" for i in range(13)]
    return base + mfcc_names
