# 分步骤实现文档 · AI 音乐情绪可视化与探索平台

> 基于 `requirement.md` 的四阶段计划，细化为可执行的 Step。每个 Step 包含目标、产物、关键实现要点、验证方式。
> 配套参照 [architecture.md](./architecture.md) 的模块划分与技术选型。

---

## 阶段总览

| 阶段 | 周期 | 核心目标 |
| --- | --- | --- |
| 一、基础搭建 | 第 1-2 周 | 环境就绪、用户系统、数据库、后端骨架 |
| 二、核心功能 | 第 3-4 周 | Apple Music 集成、AI 情绪识别、可视化 |
| 三、数据增强 | 第 5 周 | 爬虫数据采集、模型优化、AI 歌词配图 |
| 四、上线优化 | 第 6 周 | Docker 部署、多端适配、性能与体验 |

---

# 第一阶段：基础搭建（第 1-2 周）

## Step 1.1 环境准备与项目初始化

**目标**：搭好开发环境，项目骨架跑通"Hello World"。

**产物**
- `catte-music/` 项目目录
- `pyproject.toml`、`uv.lock`、`.gitignore`、`.env.example`
- 可运行的 FastAPI 空服务

**实现要点**
1. 安装系统依赖：
   ```bash
   brew install python@3.11 ffmpeg libsndfile postgresql uv
   ```
2. 初始化项目：
   ```bash
   uv init catte-music && cd catte-music
   uv venv --python 3.11
   source .venv/bin/activate
   uv add fastapi "uvicorn[standard]" sqlalchemy asyncpg psycopg2-binary \
           python-multipart python-jose passlib[bcrypt] python-dotenv
   ```
3. 建立 `app/main.py` 最小 FastAPI 应用：
   ```python
   from fastapi import FastAPI
   app = FastAPI(title="Catte Music")

   @app.get("/api/health")
   def health():
       return {"status": "ok"}
   ```
4. 配置 `.env.example`，`.gitignore` 加入 `.env`、`.venv`、`__pycache__`。

**验证**
- `uv run uvicorn app.main:app --reload` 启动，访问 `/api/health` 返回 `{"status":"ok"}`。

---

## Step 1.2 数据库设计与建表

**目标**：完成所有数据表设计，能用 SQLAlchemy 建表并读写。

**产物**
- `app/models/` 全部模型文件
- `app/database.py` 引擎与 Session
- 初始化迁移脚本

**实现要点**
1. `database.py`：创建异步引擎，支持 `DATABASE_URL` 在 SQLite/PostgreSQL 间切换。
   - 开发期：`DATABASE_URL=sqlite+aiosqlite:///./dev.db`
   - 生产期：`DATABASE_URL=postgresql+asyncpg://...`
2. 按 `architecture.md` 第四节建立模型：`User`、`Song`、`Emotion`、`EmotionDimension`、`SongEmotion`、`Tag`、`SongTag`、`UserFavorite`、`CrawlRecord`、`AiPrediction`。
3. 启动时 `Base.metadata.create_all` 自动建表（后期可上 Alembic 迁移）。

**验证**
- 写一个临时脚本插入一条用户和歌曲，查询成功返回。

---

## Step 1.3 用户注册登录与 JWT 鉴权

**目标**：前端能注册、登录，后端用 JWT 保护接口。

**产物**
- `app/api/auth.py`、`app/schemas/auth.py`、`app/utils/security.py`
- `users` 表可用

**实现要点**
1. `security.py`：`passlib[bcrypt]` 哈希密码、`python-jose` 签发/校验 JWT。
2. 注册接口 `POST /api/auth/register`：校验用户名唯一 → 哈希密码 → 入库。
3. 登录接口 `POST /api/auth/login`：校验密码 → 签发 JWT（有效期 7 天）。
4. `get_current_user` 依赖：解析 Authorization 头的 JWT，返回当前用户。

**验证**
- 用 curl 或 FastAPI 自带 `/docs` 完成 注册→登录→携带 token 访问受保护接口。

---

## Step 1.4 前端骨架与登录页

**目标**：前端工程跑通，实现登录注册页，与后端联调。

**产物**
- `frontend/` Vue/React 工程
- 登录页、注册页、API client 封装

**实现要点**
1. 用 Vite 初始化前端（React + TypeScript + Tailwind）。
2. `api/client.ts`：axios 实例，请求拦截器自动携带 JWT。
3. 登录页调用 `/api/auth/login`，成功后存 token 到 localStorage 并跳转首页。
4. 响应式布局：移动优先，Tailwind 断点适配手机/桌面。

**验证**
- 浏览器打开前端，完成注册→登录→跳转首页；Vite 代理 `/api` 到后端 8000。

---

# 第二阶段：核心功能（第 3-4 周）

## Step 2.1 Apple Music 开发者 Token 生成

**目标**：后端能生成 Apple Music Developer Token，前端能发起用户授权。

**产物**
- `app/services/apple_music/auth.py`
- `.env` 配置 `APPLE_MUSIC_KEY_ID` / `TEAM_ID` / 私钥路径

**实现要点**
1. 在 Apple Developer 后台创建 MusicKit Key，下载 `.p8` 私钥。
2. 用 `python-jose` 或 `PyJWT` 签发 JWT：Header(kid) + Payload(iss=team_id, iat, exp)。
3. 提供 `GET /api/auth/apple-music-url` 返回授权配置，前端用 MusicKit 发起授权。
4. 授权回调接口存 `Music User Token` 到 `users.apple_music_token`。

**验证**
- 前端点击"授权 Apple Music"，完成授权后后端能拿到并存储 Music User Token。

---

## Step 2.2 Apple Music API 客户端封装

**目标**：后端能调用 Apple Music API 获取用户听歌数据。

**产物**
- `app/services/apple_music/client.py`
- `app/api/apple_music.py` 路由

**实现要点**
1. `client.py`：封装 `httpx.AsyncClient`，自动携带 Developer Token + Music User Token。
2. 实现方法：`search(term)`、`get_recent_played()`、`get_heavy_rotation()`、`rate_song(id, ±1)`、`create_playlist(name, track_ids)`。
3. 路由层暴露：`GET /api/apple-music/recent`、`GET /api/apple-music/heavy-rotation`、`POST /api/apple-music/rating/{id}`。
4. 拉取的最近播放歌曲自动入库 `songs` 表（去重 by `apple_music_id`）。

**验证**
- 调用 `/api/apple-music/recent` 返回真实最近播放列表。

---

## Step 2.3 AI 情绪识别 - 特征提取

**目标**：能用 librosa 从音频提取特征向量。

**产物**
- `app/services/ai/feature.py`
- `data/audio_samples/` 测试音频

**实现要点**
1. `feature.py`：`librosa.load(path, sr=22050)` 加载音频。
2. 提取特征：`tempo`(BPM)、`spectral_centroid`(频谱质心)、`rmse`(响度)、`zero_crossing_rate`(过零率)、`mfcc`(MFCC 13 维取均值)。
3. 拼接为固定维度特征向量，归一化后返回 numpy 数组。
4. 提供 `extract_features(path) -> np.ndarray` 接口。

**验证**
- 对 3 首测试音频提取特征，打印向量维度与数值，确认稳定。

---

## Step 2.4 AI 情绪识别 - 训练与推理

**目标**：训练情绪分类器，能对歌曲给出情绪标签。

**产物**
- `app/services/ai/training.py`、`app/services/ai/classifier.py`
- `data/models/emotion_model.pkl`

**实现要点**
1. 准备训练集：50-100 首带情绪标注的音频（可用爬虫数据 + 人工标注）。
2. `training.py`：遍历训练集提取特征 → 构建特征矩阵 X 与标签 y → 训练 `RandomForestClassifier` 或 `KNN` → `joblib.dump` 导出。
3. `classifier.py`：`joblib.load` 加载模型，`predict(path) -> (emotion, confidence)`。
4. 提供 `POST /api/songs/{id}/analyze` 触发分析，结果写入 `ai_predictions` 与 `song_emotions` 表。

**验证**
- 上传/指定一首歌，调用分析接口返回情绪标签 + 置信度并入库。

---

## Step 2.5 情绪可视化（p5.js 雷达图 + 粒子动画）

**目标**：前端展示情绪雷达图与实时粒子背景。

**产物**
- `frontend/src/components/EmotionRadar.tsx`
- `frontend/src/components/ParticleBg.tsx`
- `frontend/src/pages/SongDetail.tsx`

**实现要点**
1. `GET /api/songs/{id}/radar` 返回 7 维数据（响度、高频、人声、节奏、声场、空间、层次）。
2. `EmotionRadar`：p5.js 绘制 7 边形雷达图，数值动画过渡。
3. `ParticleBg`：根据情绪主色调生成粒子，悲伤冷色（蓝/紫）、欢快暖色（橙/黄）。监听 `windowResized` 重设画布。
4. `SongDetail`：组合雷达图 + 粒子背景 + MusicKit 播放按钮；播放时背景随情绪变化。

**验证**
- 打开歌曲详情页，播放歌曲后雷达图与粒子背景正确呈现并随情绪变色。

---

# 第三阶段：数据增强（第 5 周）

## Step 3.1 反爬策略模块

**目标**：搭建可复用的反爬工具模块。

**产物**
- `app/services/crawler/anti_crawl.py`

**实现要点**
1. `random_user_agent()`：从 UA 池随机取一个浏览器 UA。
2. `random_delay(min_s, max_s)`：请求间随机休眠。
3. `ProxyPool`：维护代理 IP 列表，`get()` 轮换返回。
4. `make_session()`：返回带随机 UA、超时、重试的 `requests.Session`。

**验证**
- 单元测试：连续调用返回不同 UA、延时在区间内。

---

## Step 3.2 Apple Music 评分爬虫

**目标**：批量采集歌曲评分与标签数据。

**产物**
- `app/services/crawler/ratings.py`
- `data/raw/ratings/` 输出文件

**实现要点**
1. `ratings.py`：调用 `make_session()`，分页请求目标页面，BeautifulSoup 解析歌名/歌手/专辑/评分/标签。
2. 去重入库 `songs` + `song_tags`，记录 `crawl_records`。
3. 支持断点续爬：记录已爬页码，失败可从上次继续。

**验证**
- 爬取 1 页数据正确入库，再爬 100 页稳定无封禁。

---

## Step 3.3 Apple Music 评论爬虫（JS 逆向）

**目标**：采集歌曲评论用于情感分析验证。

**产物**
- `app/services/crawler/comments.py`
- JS 加密逻辑还原

**实现要点**
1. 分析评论接口的 `params` 与 `encSecKey` 加密流程（AES + RSA）。
2. 用 `pycryptodome` 实现 `encrypt_params()` 还原加密参数。
3. `comments.py`：构造加密请求 → 解析评论 JSON → 提取内容/点赞/用户。
4. 多线程抓取，控制并发避免触发风控。

**验证**
- 对一首歌抓取评论，输出评论列表 JSON 与数据库记录一致。

---

## Step 3.4 模型优化与扩充训练

**目标**：用爬虫数据扩充训练集，提升模型准确率。

**产物**
- 更新后的 `emotion_model.pkl`
- 训练准确率报告

**实现要点**
1. 合并现有音频特征 + 爬虫标签作为训练数据。
2. 尝试不同分类器（RandomForest / GradientBoosting / SVM），交叉验证选最优。
3. 输出 `classification_report`（precision/recall/f1），记录模型版本到 `ai_predictions.model_version`。

**验证**
- 对比新旧模型在测试集上的 f1，确认有提升。

---

## Step 3.5 AI 歌词配图功能

**目标**：播放歌曲时按歌词段落自动生成配图。

**产物**
- `app/services/ai/lyrics_image.py`
- `frontend/src/pages/LyricsGallery.tsx`

**实现要点**
1. 后端获取歌词文本（Apple Music API 或歌词源），按段落切分。
2. 调用 AI 图像生成 API（Stable Diffusion / Replicate），为每段生成配图，缓存到本地。
3. `GET /api/songs/{id}/lyrics-gallery` 返回 `[{lyrics, image_url}, ...]`。
4. 前端画廊展示，歌词与配图同步滚动。

**验证**
- 打开歌词画廊页，每段歌词对应一张意境匹配的配图。

---

# 第四阶段：上线与优化（第 6 周）

## Step 4.1 Docker 容器化

**目标**：一键 `docker-compose up` 启动整套服务。

**产物**
- `docker/Dockerfile`、`docker/docker-compose.yml`
- `.dockerignore`

**实现要点**
1. Dockerfile：`python:3.11-slim` + `ffmpeg`/`libsndfile1` + `uv sync` 装依赖 + 复制源码。
2. compose 定义 `web`、`db`、`frontend` 三个服务，`db` 健康检查后启动 `web`。
3. 数据卷持久化 PostgreSQL；`.env` 通过 `env_file` 注入。
4. 前端构建产物由 nginx 容器托管，反代 `/api` 到 web:8000。

**验证**
- 全新机器 `docker-compose up --build` 后访问 `http://localhost` 可用。

---

## Step 4.2 多端适配打磨

**目标**：iOS Safari 与桌面浏览器体验一致。

**产物**
- 响应式样式修复、p5.js 移动端适配

**实现要点**
1. 视口高度用 `100dvh` 替代 `100vh` 修复 Safari 地址栏问题。
2. p5.js 画布在 `touchStarted/touchMoved` 触发交互；移动端降低粒子数保帧率。
3. MusicKit 授权改重定向式，避免 iOS 弹窗拦截。
4. 音频 autoplay 需用户首次点击后触发，WebAudio `resume()`。

**验证**
- iPhone 连 Mac 用 Safari Web Inspector 真机调试，播放/授权/可视化均正常。

---

## Step 4.3 性能优化

**目标**：接口响应快、无明显卡顿。

**产物**
- 缓存策略、异步任务、索引

**实现要点**
1. 情绪预测结果缓存到 `ai_predictions`，避免重复推理。
2. 耗时 AI 分析改异步：接口返回 task_id，前端轮询结果（后期可用 Redis + RQ）。
3. 数据库加索引：`songs.apple_music_id`、外键列、`ai_predictions.song_id`。
4. 前端图片懒加载、p5.js 用 `requestAnimationFrame`。

**验证**
- 重复请求同一歌曲情绪接口，响应 < 100ms（命中缓存）。

---

## Step 4.4 扩展功能与收尾

**目标**：补齐小型功能，完成作品集整理。

**产物**
- 歌曲收藏、情绪日记、每周听歌报告
- README 与作品集说明

**实现要点**
1. 收藏：`POST/DELETE /api/favorites`，前端收藏页。
2. 情绪日记：用户每日记录心情 + 关联歌曲，`emotion_diary` 表。
3. 每周报告：聚合本周听歌情绪分布，生成雷达图趋势。
4. 更新 README：安装、启动、架构说明、截图。

**验证**
- 完整走通：授权→听歌→情绪画像→收藏→每周报告，全流程无报错。

---

## 实施检查清单

- [ ] Step 1.1 环境与骨架可跑
- [ ] Step 1.2 数据库建表成功
- [ ] Step 1.3 注册登录联调通过
- [ ] Step 1.4 前端登录页可用
- [ ] Step 2.1 Apple Music 授权走通
- [ ] Step 2.2 听歌数据接口可用
- [ ] Step 2.3 音频特征提取稳定
- [ ] Step 2.4 情绪分类器训练完成
- [ ] Step 2.5 可视化页面呈现
- [ ] Step 3.1 反爬模块就绪
- [ ] Step 3.2 评分爬虫跑通
- [ ] Step 3.3 评论爬虫跑通
- [ ] Step 3.4 模型准确率提升
- [ ] Step 3.5 歌词配图可用
- [ ] Step 4.1 Docker 一键启动
- [ ] Step 4.2 移动端真机测试通过
- [ ] Step 4.3 性能优化验证
- [ ] Step 4.4 扩展功能与文档收尾

---

*按 Step 顺序逐步推进，每个 Step 完成后在检查清单打勾并提交 Git，确保可随时回退。*
