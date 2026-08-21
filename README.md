<div align="center">

# 🎵 catte — AI 音乐情绪可视化与探索平台

**AI Music Emotion Visualization & Discovery Platform**

**用 AI 解析每首歌的情绪，用粒子与雷达图可视化呈现你的听歌画像**

**[English](./README.md#en) | [中文](./README.md#zh)**

</div>

---

<a id="zh"></a>

## 🇨🇳 中文版

### ✨ 核心功能

**1. AI 音乐情绪识别**

基于 `librosa` 从音频中提取声学特征（响度、频谱、节奏、声场等），`scikit-learn` 多标签分类模型将歌曲映射到 **20 种情绪标签**（治愈、甜蜜、孤独、狂野、热血、宁静……）。分析结果包含：主情绪 + 置信度、多个次情绪徽章、情绪模糊提示、完整情绪概率分布；数据来自网易云真实歌曲采集训练，稀缺情绪由标准模板兜底。

**2. 情绪雷达图（7 维可视化）**

从 **响度、高频、节奏、声场、层次、舒缓、韵律** 7 个维度刻画歌曲画像。霓虹渐变填充 + 发光节点 + 辉光描边的赛博风格；叠加该情绪的标准模板画像（虚线轮廓）与歌曲实测实时对比，一眼看出歌曲与典型情绪的贴近程度；每个维度附动态文字解析与情绪模板参考值。

**3. 沉浸式情绪可视化**

p5.js 粒子背景随歌曲情绪主色调实时变色流动（拖尾 + 辉光）；深空黑 + 霓虹紫/电光蓝/赛博粉/辉光青 + 玻璃拟态（Glassmorphism）的年轻化界面；移动端自动降低粒子密度，保证帧率流畅。

**4. 多平台接入**

- **Apple Music**：官方 MusicKit 授权集成，同步最近播放、音乐库、重播榜单、全站搜索
- **网易云音乐**：扫码登录 → 搜索 → 30s 试听 → AI 情绪分析；持续采集真实歌曲与评论数据用于模型训练迭代

**5. 社区分享与互动推荐**

AI 分析完成即可分享/推荐专辑与歌单；首页推荐完全来自其他用户的分享，按 **7 维情绪余弦相似度**优先推荐"口味相近"的内容，**点赞数加权**，不足时随机兜底补足；平台来源匹配——已绑定 Apple Music / 网易云的用户才会收到对应来源的推荐。

**6. 用户主页与点赞**

点击分享者即可进入其主页查看全部歌单与分享；对喜欢的分享点赞 / 取消点赞，为"群体口味"提供曝光信号。

---

### 🛠 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy · SQLite / PostgreSQL |
| AI | librosa 特征提取 · scikit-learn（HistGBDT 多标签分类）· 真实数据训练 + 模板兜底 · joblib 模型持久化 |
| 前端 | React · TypeScript · Vite · Tailwind CSS · p5.js |
| 部署 | Docker · docker-compose |

### 🚀 本地启动

```bash
# 后端（catte-music 目录）
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev

# 打开 http://localhost:5173
```

---

<a id="en"></a>

## 🇬🇧 English

### ✨ Features

**1. AI Music Emotion Recognition**

Extracts acoustic features (loudness, spectrum, rhythm, soundstage, etc.) from audio with `librosa`, then maps each song to **20 emotion tags** (Healing, Sweet, Lonely, Wild, Passionate, Serene…) via a multi-label `scikit-learn` classifier. Each analysis returns: primary emotion + confidence, secondary emotion badges, fuzzy-emotion hints, and the full probability distribution. The model is trained on real songs collected from NetEase Cloud Music, with built-in emotion templates as fallback for rare classes.

**2. Emotion Radar (7-Dimensional Visualization)**

Profiles each song across **Loudness, High Frequency, Rhythm, Soundstage, Layering, Soothing, and Prosody**. Rendered in a cyberpunk style with neon gradient fills, glowing nodes, and luminous outlines. The primary emotion's standard template is overlaid as a dashed outline for instant comparison with the song's actual profile — plus a per-dimension textual interpretation with template reference values.

**3. Immersive Emotion Visualization**

A p5.js particle background flows and shifts color in real time to match the song's dominant emotion (with trails and glow). The whole UI follows a deep-space black + neon purple/blue/pink/cyan Glassmorphism design for a youthful vibe; particle density drops automatically on mobile for smooth performance.

**4. Multi-Platform Integration**

- **Apple Music**: Official MusicKit authorization — sync Recent Plays, Library, Heavy Rotation, and full catalog search
- **NetEase Cloud Music**: QR login → search → 30-second preview → AI emotion analysis; continuously collects real song & comment data to retrain the model

**5. Community Sharing & Social Recommendation**

After AI analysis, share albums/playlists with the community. The homepage feed is driven entirely by other users' shares, ranked by **7-dimensional emotion cosine similarity** (taste-matching first), weighted by **likes**, and topped up randomly when needed. Platform matching ensures users only see shares from platforms they've bound (Apple Music / NetEase).

**6. User Profiles & Likes**

Click any sharer to visit their profile and browse all of their playlists and shares; like / unlike posts to boost exposure for collective taste.

---

### 🛠 Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy · SQLite / PostgreSQL |
| AI | librosa feature extraction · scikit-learn (HistGBDT multi-label) · real-data training + template fallback · joblib persistence |
| Frontend | React · TypeScript · Vite · Tailwind CSS · p5.js |
| Deployment | Docker · docker-compose |

### 🚀 Quick Start

```bash
# Backend (inside catte-music/)
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Open http://localhost:5173
```
