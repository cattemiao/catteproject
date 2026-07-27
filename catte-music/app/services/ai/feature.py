"""librosa 音频特征提取。

提取节奏(BPM)、响度、频谱质心、过零率、MFCC(13维均值)、Chroma(12维均值)、Tonnetz(6维均值)等声学特征。
支持离线预处理缓存。
"""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np


def extract_features(file_path: str | Path, sr: int = 22050) -> np.ndarray:
    """加载音频并提取固定维度特征向量。

    Returns:
        一维 numpy 数组，结构：
        [tempo, rmse_mean, spectral_centroid_mean, zcr_mean,
         mfcc_0..mfcc_12,              ← 13 维
         chroma_0..chroma_11,          ← 12 维
         tonnetz_0..tonnetz_5]         ← 6 维
        共 35 维。
    """
    y, _sr = librosa.load(str(file_path), sr=sr, mono=True)

    # 节奏 BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=_sr)

    # 响度 (RMS 均值)
    rmse = librosa.feature.rms(y=y)

    # 频谱质心均值
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=_sr)

    # 过零率均值
    zcr = librosa.feature.zero_crossing_rate(y)

    # MFCC 13 维取均值
    mfcc = librosa.feature.mfcc(y=y, sr=_sr, n_mfcc=13)

    # Chroma 12 维取均值（半音阶能量分布 → 和声色彩）
    chroma = librosa.feature.chroma_stft(y=y, sr=_sr, n_chroma=12)

    # Tonnetz 6 维取均值（调性网络 → 大小调区分）
    tonnetz = librosa.feature.tonnetz(y=y, sr=_sr)

    features = np.concatenate(
        [
            np.array([float(tempo)]),
            np.array([float(rmse.mean())]),
            np.array([float(spectral_centroid.mean())]),
            np.array([float(zcr.mean())]),
            mfcc.mean(axis=1),       # 13 维
            chroma.mean(axis=1),     # 12 维
            tonnetz.mean(axis=1),    # 6 维
        ]
    )
    return features


CACHED_FEATURES: dict[str, np.ndarray] = {}


def extract_features_cached(file_path: str | Path, sr: int = 22050) -> np.ndarray:
    """带缓存的特征提取，避免重复计算。"""
    key = str(file_path)
    if key not in CACHED_FEATURES:
        CACHED_FEATURES[key] = extract_features(file_path, sr)
    return CACHED_FEATURES[key]


def feature_names() -> list[str]:
    """返回特征名列表，与 extract_features 输出维度一一对应。"""
    base = ["tempo", "rmse_mean", "spectral_centroid_mean", "zcr_mean"]
    mfcc_names = [f"mfcc_{i}" for i in range(13)]
    chroma_names = [f"chroma_{i}" for i in range(12)]
    tonnetz_names = [f"tonnetz_{i}" for i in range(6)]
    return base + mfcc_names + chroma_names + tonnetz_names