"""librosa 音频特征提取（情绪算法 v2 特征集）。

v2 将特征从 35 维增强到 65 维，新增：
- delta MFCC 均值 / MFCC std（时序动态与能量波动）
- 频谱平坦度 spectral_flatness（噪音/乐音占比）
- 能量熵 energy_entropy（频谱能量分布复杂度）
- onset rate（起音密度，节奏急缓）
- spectral rolloff（高频能量截止点）

布局（共 65 维）：
    [tempo, rmse_mean, centroid_mean, zcr_mean,            ← 4
     flatness_mean, rolloff_mean, energy_entropy, onset_rate, ← 4
     mfcc_0..12 mean(13), mfcc_0..12 std(13), delta_mfcc_0..12 mean(13),
     chroma_0..11(12), tonnetz_0..5(6)]                    ← 65

新增特征全部为 CPU 毫秒级计算，保持轻量。
"""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

# 特征维度常量：供其他模块判断特征向量新旧版本（旧 35 维 → 新 65 维）
FEATURE_DIM = 65
LEGACY_FEATURE_DIM = 35


def _energy_entropy(spectrogram: np.ndarray, n_blocks: int = 10) -> float:
    """频谱能量分块香农熵：衡量频谱能量分布的均匀程度。

    熵越高 → 能量在各频段分布越均匀（如白噪音/氛围），越低 → 能量集中在少数频段。
    """
    frame_energy = np.sum(spectrogram**2, axis=0)
    total = frame_energy.sum()
    if total <= 0:
        return 0.0
    # 按帧切块（块数不足时退化为整体单块）
    n = len(frame_energy)
    if n < n_blocks:
        blocks = [frame_energy.sum()]
    else:
        bounds = np.linspace(0, n, n_blocks + 1, dtype=int)
        blocks = [frame_energy[bounds[i] : bounds[i + 1]].sum() for i in range(n_blocks)]
    p = np.array(blocks, dtype=float) / total
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum() / np.log2(max(len(p), 1)))


def extract_features(file_path: str | Path, sr: int = 22050) -> np.ndarray:
    """加载音频并提取 65 维特征向量（情绪算法 v2 特征集）。

    Returns:
        一维 numpy 数组，结构见模块 docstring，共 65 维。
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

    # ── v2 新增标量特征 ──
    # 频谱平坦度（乐音 vs 噪音占比；纯音低、白噪音高）
    flatness = librosa.feature.spectral_flatness(y=y)
    # 高频能量截止点（85% 能量频率，均值）
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=_sr)
    # 频谱能量熵（STFT 幅度谱）
    stft = librosa.stft(y=y)
    energy_entropy = _energy_entropy(np.abs(stft))
    # 起音密度（每秒 onset 个数）
    onset_frames = librosa.onset.onset_detect(y=y, sr=_sr)
    onset_rate = float(len(onset_frames) / max(len(y) / _sr, 1e-6))

    # MFCC 13 维均值 + std + delta 均值
    mfcc = librosa.feature.mfcc(y=y, sr=_sr, n_mfcc=13)
    mfcc_delta = librosa.feature.delta(mfcc)

    # Chroma 12 维均值（半音阶能量分布 → 和声色彩）
    chroma = librosa.feature.chroma_stft(y=y, sr=_sr, n_chroma=12)

    # Tonnetz 6 维均值（调性网络 → 大小调区分）
    tonnetz = librosa.feature.tonnetz(y=y, sr=_sr)

    features = np.concatenate(
        [
            np.array([float(tempo)]),
            np.array([float(rmse.mean())]),
            np.array([float(spectral_centroid.mean())]),
            np.array([float(zcr.mean())]),
            np.array([float(flatness.mean())]),
            np.array([float(rolloff.mean())]),
            np.array([energy_entropy]),
            np.array([onset_rate]),
            mfcc.mean(axis=1),        # 13 维
            mfcc.std(axis=1),         # 13 维
            mfcc_delta.mean(axis=1),  # 13 维
            chroma.mean(axis=1),      # 12 维
            tonnetz.mean(axis=1),     # 6 维
        ]
    )
    assert features.shape[0] == FEATURE_DIM, f"特征维度异常: {features.shape[0]}"
    return features


CACHED_FEATURES: dict[str, np.ndarray] = {}


def extract_features_cached(file_path: str | Path, sr: int = 22050) -> np.ndarray:
    """带缓存的特征提取，避免重复计算。"""
    key = str(file_path)
    if key not in CACHED_FEATURES:
        CACHED_FEATURES[key] = extract_features(file_path, sr)
    return CACHED_FEATURES[key]


def feature_names() -> list[str]:
    """返回特征名列表，与 extract_features 输出维度一一对应（65 维）。"""
    base = [
        "tempo", "rmse_mean", "spectral_centroid_mean", "zcr_mean",
        "flatness_mean", "rolloff_mean", "energy_entropy", "onset_rate",
    ]
    mfcc_mean = [f"mfcc_{i}_mean" for i in range(13)]
    mfcc_std = [f"mfcc_{i}_std" for i in range(13)]
    mfcc_delta = [f"delta_mfcc_{i}_mean" for i in range(13)]
    chroma_names = [f"chroma_{i}" for i in range(12)]
    tonnetz_names = [f"tonnetz_{i}" for i in range(6)]
    return base + mfcc_mean + mfcc_std + mfcc_delta + chroma_names + tonnetz_names


# ─────────────────── 特征 → 7 维情绪指标映射 ───────────────────
# 旧布局（35 维）与新布局（65 维）索引差异：
#   35 维: base[0:4], mfcc[4:17], chroma[17:29], tonnetz[29:35]
#   65 维: base[0:8], mfcc[8:21], chroma[47:59], tonnetz[59:65]

def _feature_slices(dim: int) -> tuple[slice, slice, slice]:
    if dim == LEGACY_FEATURE_DIM:
        return slice(4, 17), slice(17, 29), slice(29, 35)
    return slice(8, 21), slice(47, 59), slice(59, 65)


def map_to_dimensions(features: np.ndarray) -> np.ndarray:
    """65 维音频特征 → 7 维情绪指标（新标定空间，雷达图展示使用）。

    系数按真实特征分布标定：典型歌曲各维度落于 30-85，极端才接近 0/100。
    兼容旧 35 维特征向量（迁移场景）。
    """
    dim = features.shape[0]
    mfcc_s, chroma_s, tonnetz_s = _feature_slices(dim)
    tempo, rmse, centroid, zcr = features[0], features[1], features[2], features[3]
    mfcc = features[mfcc_s]
    chroma = features[chroma_s]
    tonnetz = features[tonnetz_s]

    loudness = min(100, max(0, rmse * 240))
    high_freq = min(100, max(0,
        (centroid / 5000) * 100 +
        float(np.mean(chroma[6:])) * 50 - 10
    ))
    rhythm = min(100, max(0, tempo * 0.5))
    soundstage = min(100, max(0,
        30 + float(np.std(mfcc[4:10])) * 5 +
        float(np.std(chroma)) * 30
    ))
    layering = min(100, max(0,
        float(np.std(mfcc)) * 1.2 +
        float(np.std(tonnetz)) * 40
    ))
    soothing = min(100, max(0,
        85 - rmse * 150 -
        (centroid / 5000) * 20 +
        float(np.mean(chroma[:4])) * 25
    ))
    prosody = min(100, max(0,
        25 + float(np.std(mfcc[2:8])) * 4 +
        (zcr * 40) +
        float(np.std(tonnetz)) * 30
    ))

    return np.array([loudness, high_freq, rhythm, soundstage, layering, soothing, prosody])


def map_to_dimensions_legacy(features: np.ndarray) -> np.ndarray:
    """特征 → 7 维情绪指标（旧饱和空间，仅供模板匹配分类使用）。

    情绪模板按旧空间标定，保持分类结果稳定；展示用的维度请用
    `map_to_dimensions`（新标定空间，幅度更分散）。
    """
    dim = features.shape[0]
    mfcc_s, chroma_s, tonnetz_s = _feature_slices(dim)
    tempo, rmse, centroid, zcr = features[0], features[1], features[2], features[3]
    mfcc = features[mfcc_s]
    chroma = features[chroma_s]
    tonnetz = features[tonnetz_s]

    loudness = min(100, max(0, rmse * 1000))
    high_freq = min(100, max(0,
        (centroid / 5000) * 55 +
        float(np.mean(mfcc[:4])) * 5 +
        float(np.mean(chroma[6:])) * 35
    ))
    rhythm = min(100, max(0, tempo * 0.8))
    soundstage = min(100, max(0,
        45 + float(np.std(mfcc[4:10])) * 3 +
        float(np.std(chroma)) * 20
    ))
    layering = min(100, max(0,
        35 + float(np.std(mfcc)) * 4 +
        float(np.std(tonnetz)) * 15
    ))
    soothing = min(100, max(0,
        100 - rmse * 750 -
        (centroid / 5000) * 28 +
        float(np.mean(chroma[:4])) * 25
    ))
    prosody = min(100, max(0,
        25 + float(np.std(mfcc[2:8])) * 3.5 +
        (zcr * 75) +
        float(np.std(tonnetz)) * 12
    ))
    return np.array([loudness, high_freq, rhythm, soundstage, layering, soothing, prosody])


def template_distances(features: np.ndarray) -> dict[str, float]:
    """特征到 20 类情绪模板的欧氏距离（旧饱和空间）。

    返回 {情绪名: 距离}，供模板兜底与迁移伪概率使用。
    """
    from app.services.ai.seed_emotions import EMOTION_PROFILES

    audio_dim = map_to_dimensions_legacy(features)
    distances: dict[str, float] = {}
    for name, _, dims in EMOTION_PROFILES:
        template = np.array([
            dims["loudness"], dims["high_freq"], dims["rhythm"],
            dims["soundstage"], dims["layering"], dims["soothing"], dims["prosody"],
        ])
        distances[name] = float(np.linalg.norm(audio_dim - template))
    return distances


def template_probs(features: np.ndarray, temperature: float = 25.0) -> dict[str, float]:
    """模板距离 → 20 维伪概率（softmax(-dist/τ)）。

    用于：旧数据迁移（无音频重分析时）、类样本不足的混合兜底。
    """
    distances = template_distances(features)
    probs = {name: np.exp(-d / temperature) for name, d in distances.items()}
    total = sum(probs.values())
    if total <= 0:
        return {name: 1.0 / len(probs) for name in probs}
    return {name: p / total for name, p in probs.items()}
