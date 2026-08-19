# 系统架构文档 · AI 音乐情绪可视化与探索平台

> 本文档基于 `requirement.md` 梳理系统的整体架构、模块划分、数据模型、API 设计与部署方案，作为开发的蓝图。

---

## 一、架构总览

平台采用前后端分离 + 服务化模块架构，整体分为四层：表现层、应用服务层、领域服务层、数据层。

```
┌─────────────────────────────────────────────────────────────┐
│                    表现层 Presentation                       │
│   桌面浏览器 / 移动端浏览器 (iOS Safari)                      │
│   React/Vue + p5.js 可视化 + Tailwind CSS 响应式             │
│   炫酷现代年轻风格：深色霓虹 + 毛玻璃发光 + 粒子动态           │
│   MusicKit on the Web (Apple Music 授权与播放)               │
└──────────────────────────┬──────────────────────────────────┘
                           │ RESTful / JSON
┌──────────────────────────┴──────────────────────────────────┐
│                 应用服务层 Application                       │
│             FastAPI 后端 (统一 API 网关)                     │
│   用户认证 · 歌曲管理 · 情绪查询 · 分享互动 · 推荐接口        │
└───────┬──────────────┬──────────────┬───────────────────────┘
        │              │              │
┌───────┴──────┐ ┌─────┴──────┐ ┌─────┴──────────────┐
│  爬虫服务     │ │ AI 分析服务 │ │ Apple Music 集成   │
│  Crawler     │ │  AI Engine  │ │  Apple Music API   │
│ 评分/评论抓取 │ │ 特征提取/预测│ │  授权/听歌数据/    │
│ requests+BS4 │ │ librosa+skl │ │  播放列表管理      │
└───────┬──────┘ └─────┬──────┘ └─────┬──────────────┘
        │              │              │
┌───────┴──────────────┴──────────────┴──────────────────────┐
│                    数据层 Data                               │
│   PostgreSQL (主库) · SQLite (开发初期) · 文件存储(模型/爬取) │
└─────────────────────────────────────────────────────────────┘
```

### 设计原则
- **单一语言栈**：后端统一 Python，爬虫/AI/API 共享代码与依赖。
- **关注点分离**：爬虫、AI、Apple Music 集成各自独立模块，互不耦合。
- **环境一致**：本地用 brew + uv 开发，生产用 Docker 部署，配置驱动切换。
- **移动优先**：前端响应式设计，iOS Safari 与桌面浏览器双端可用。

---

## 二、技术栈

| 层级 | 技术选型 | 说明 |
| --- | --- | --- |
| 前端框架 | React 或 Vue 3 | SPA 单页应用 |
| 可视化 | p5.js | 情绪雷达图、粒子动画实时渲染 |
| 样式 | Tailwind CSS | 移动优先响应式布局 |
| 音乐播放/授权 | MusicKit on the Web | Apple Music OAuth 与播放控制 |
| 后端框架 | FastAPI (首选) | 异步、自带 OpenAPI 文档、类型友好 |
| ASGI 服务器 | Uvicorn | 生产部署 |
| ORM | SQLAlchemy 2.0 | 统一操作 SQLite/PostgreSQL |
| 数据库驱动 | asyncpg / psycopg2 | 异步生产 / 同步开发 |
| 数据库 | PostgreSQL (生产) / SQLite (开发初期) | 关系型，支持 JSONB |
| 音频特征提取 | librosa | 节奏、频谱质心、MFCC 等 |
| 机器学习 | scikit-learn | 情绪分类器，joblib 持久化模型 |
| 爬虫 | requests + BeautifulSoup + lxml | 评分/评论抓取 |
| JS 逆向 | pycryptodome | 破解加密参数 |
| Python 环境管理 | brew + uv | 系统依赖 + Python 版本/依赖管理 |
| 容器化 | Docker + docker-compose | web + db 容器编排 |

---

## 三、模块设计

### 3.1 后端目录结构（FastAPI 项目）

```
catte-music/
├── app/
│   ├── main.py                  # FastAPI 入口，挂载路由
│   ├── config.py                # 配置管理（env 读取）
│   ├── database.py              # SQLAlchemy 引擎与 Session
│   ├── models/                  # 数据库模型
│   │   ├── user.py
│   │   ├── song.py
│   │   ├── emotion.py
│   │   └── ...
│   ├── schemas/                 # Pydantic 请求/响应模型
│   ├── api/                     # 路由层
│   │   ├── auth.py              # 用户注册登录
│   │   ├── songs.py             # 歌曲增删改查
│   │   ├── emotions.py          # 情绪查询/雷达图数据
│   │   ├── shares.py            # 分享与点赞
│   │   ├── recommend.py         # 推荐列表(用户分享驱动)
│   │   ├── users.py             # 用户主页歌单
│   │   └── apple_music.py       # Apple Music 代理与听歌数据
│   ├── services/                # 业务逻辑层
│   │   ├── crawler/             # 爬虫服务
│   │   │   ├── douban.py        # (已统一为 Apple Music 评分)
│   │   │   ├── comments.py      # 评论抓取
│   │   │   └── anti_crawl.py    # 反爬策略(随机UA/延时/代理)
│   │   ├── ai/                  # AI 引擎
│   │   │   ├── feature.py       # librosa 特征提取
│   │   │   ├── classifier.py    # scikit-learn 分类器
│   │   │   └── training.py      # 模型训练与导出
│   │   ├── apple_music/         # Apple Music 集成
│   │   │   ├── auth.py          # Token 生成与管理
│   │   │   └── client.py        # API 调用封装
│   │   ├── share.py             # 分享与点赞服务
│   │   └── recommend.py         # 推荐流水线(平台过滤+情绪相似度+点赞加权+随机兜底)
│   └── utils/
├── frontend/                    # 前端工程
│   └── src/
├── data/                        # 爬取数据、训练集、模型文件
│   ├── raw/                     # 原始爬取数据
│   ├── models/                  # 训练好的 .pkl 模型
│   └── audio_samples/           # 音频样本
├── tests/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── pyproject.toml               # uv 管理依赖
├── uv.lock
└── .env                         # 环境变量(不入库)
```

### 3.2 核心模块职责

#### 爬虫服务 `services/crawler/`
- **职责**：采集 Apple Music 评分数据与评论数据，输出结构化 JSON/CSV 供 AI 训练和数据库入库。
- **反爬策略模块** `anti_crawl.py`：随机 User-Agent 池、随机延时休眠、代理 IP 轮换、Session/Cookie 维护。
- **评论爬虫** `comments.py`：JS 逆向还原 `params`/`encSecKey` 加密逻辑（基于 AES/RSA）。
- **输出**：写入 `data/raw/` 并入库 `crawl_records` 表。

#### AI 引擎 `services/ai/`
- **特征提取** `feature.py`：用 librosa 加载音频，提取节奏(BPM)、响度、频谱质心、MFCC、过零率等声学特征向量。
- **分类器** `classifier.py`：加载 `data/models/emotion_model.pkl`，输入特征向量输出情绪标签与置信度。
- **训练流程** `training.py`：从训练集提取特征 → 标注情绪标签 → 训练 scikit-learn 分类器 → joblib 导出模型。
- **情绪标签体系**：甜蜜、浪漫、治愈、孤独、悲伤、深情、欢快、愤怒、宁静、热血 等 15 种。

#### Apple Music 集成 `services/apple_music/`
- **认证** `auth.py`：生成开发者 Token (JWT)，管理 Music User Token(OAuth 授权流程)。
- **客户端** `client.py`：封装 API 调用——搜索、获取最近播放、获取个人库、创建播放列表、为歌曲打分(±1)。
- **前端配合**：前端用 MusicKit on the Web 发起用户授权，后端代理部分 API 调用以保护密钥。

#### 分享与互动服务 `services/share.py` + `services/recommend.py`
- **分享** `share.py`：创建分享（校验 AI 分析结果存在）、点赞/取消点赞（`likes` 联合唯一）。
- **推荐流水线** `recommend.py`：`平台过滤 → 情绪相似度排序 → 点赞加权 → 随机兜底补足`，产出当前用户的推荐列表（完全来自其他用户的分享）。
- **情绪相似度**：聚合当前用户 AI 分析结果的 7 维情绪向量，与各分享内容的向量计算余弦相似度。

#### 应用服务 `api/`
- 对前端暴露 RESTful 接口，组合调用下层领域服务。
- 认证基于 JWT（用户注册登录后签发）。

---

## 四、数据模型设计

### ER 概览

```
users 1───* user_favorites *───1 songs
                                  |
                          *───────┴───────*
                          |               |
                    song_emotions    song_tags
                          |               |
                    emotions 1     tags 1
                          |
                 emotion_dimensions (7维可视化)

users 1───* shares *───1 songs        （分享：用户 → 专辑/播放列表）
users 1───* likes *───1 shares        （点赞：用户对分享点赞，联合唯一）

crawl_records (爬虫采集记录)
ai_predictions (AI 预测结果)
```

### 关键表结构

#### users
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | 用户ID |
| username | varchar | 用户名 |
| password_hash | varchar | 密码哈希 |
| apple_music_token | text | Music User Token |
| created_at | timestamp | |

#### songs
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | |
| apple_music_id | varchar | Apple Music 歌曲标识 |
| title | varchar | 歌名 |
| artist | varchar | 歌手 |
| album | varchar | 专辑 |
| duration_ms | int | 时长 |
| raw_meta | jsonb | Apple Music 原始元数据 |

#### emotions
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | |
| name | varchar | 情绪名(治愈/悲伤...) |
| color | varchar | 对应主色调 |

#### emotion_dimensions
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | |
| emotion_id | FK | |
| loudness | float | 响度 |
| high_freq | float | 高频 |
| vocal | float | 人声 |
| rhythm | float | 节奏 |
| soundstage | float | 声场 |
| space | float | 空间 |
| layering | float | 层次 |

#### song_emotions（歌曲-情绪 多对多）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| song_id | FK | |
| emotion_id | FK | |
| confidence | float | AI 置信度 0-1 |

#### song_tags（歌曲-标签 多对多）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| song_id | FK | |
| tag_id | FK | |
| source | varchar | 来源(crawler/user/ai) |

#### user_favorites（原"收藏"，演进为对分享点赞，见 likes）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | FK | |
| song_id | FK | |

#### shares（分享/推荐记录）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | |
| user_id | FK | 分享者 |
| song_id | FK | 被分享的专辑/播放列表 |
| platform | varchar | 来源平台 apple / netease |
| comment | varchar | 分享语（可选） |
| created_at | timestamp | |

#### likes（点赞记录）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | |
| share_id | FK | 被点赞的分享 |
| user_id | FK | 点赞者 |
| created_at | timestamp | |
| UNIQUE(user_id, share_id) | | 每人每条分享只能点赞一次 |

#### crawl_records
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | |
| source | varchar | 数据来源 |
| target_id | varchar | 抓取目标 |
| status | varchar | success/failed |
| crawled_at | timestamp | |

#### ai_predictions
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | PK | |
| song_id | FK | |
| emotion_id | FK | |
| confidence | float | |
| feature_vector | jsonb | 特征向量 |
| model_version | varchar | |
| predicted_at | timestamp | |

---

## 五、API 设计（核心接口）

### 认证
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/auth/apple-music-url` | 获取 Apple Music 授权链接 |
| POST | `/api/auth/apple-music-callback` | 授权回调，存 token |

### 歌曲与情绪
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/songs` | 歌曲列表(分页/搜索) |
| GET | `/api/songs/{id}` | 歌曲详情 |
| GET | `/api/songs/{id}/emotion` | 歌曲情绪预测结果 |
| GET | `/api/songs/{id}/radar` | 7 维情绪雷达图数据 |
| POST | `/api/songs/{id}/analyze` | 触发 AI 分析(异步) |

### 分享与推荐（用户互动）
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/shares` | 分享专辑/播放列表（需已有 AI 分析结果） |
| GET | `/api/recommend` | 推荐列表（平台过滤 + 情绪相近优先 + 点赞加权 + 随机兜底补足） |
| POST | `/api/shares/{id}/like` | 点赞分享 |
| DELETE | `/api/shares/{id}/like` | 取消点赞 |
| GET | `/api/users/{id}/songs` | 用户主页全部歌单（点击推荐卡片分享者进入） |

> 原"收藏"功能演进为"点赞"互动：点赞作用于分享内容，点赞数越多，推荐优先级越高。

### Apple Music 数据
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/apple-music/recent` | 最近播放记录 |
| GET | `/api/apple-music/heavy-rotation` | 高频播放 |
| POST | `/api/apple-music/rating/{song_id}` | 为歌曲打分 |

---

## 六、前端架构

### 页面与组件
```
frontend/src/
├── pages/
│   ├── Home.tsx            # 首页(情绪可视化总览)
│   ├── Login.tsx           # 登录/注册
│   ├── AppleMusicAuth.tsx  # 授权回调页
│   ├── SongDetail.tsx      # 歌曲详情(雷达图+粒子动画)
│   ├── LyricsGallery.tsx   # AI 歌词配图画廊
│   ├── EmotionReport.tsx   # 每周情绪听歌报告
│   ├── Favorites.tsx       # 我的收藏
│   ├── ShareFeed.tsx       # 推荐列表（其他用户的分享，情绪相近优先）
│   └── UserProfile.tsx     # 用户主页（查看其全部歌单）
├── components/
│   ├── EmotionRadar.tsx    # 情绪雷达图(p5.js)
│   ├── ParticleBg.tsx      # 情绪粒子背景(p5.js)
│   ├── MusicPlayer.tsx     # MusicKit 播放器封装
│   ├── ShareCard.tsx       # 分享卡片（分享者信息 + 点赞按钮 + 情绪徽章）
│   └── Layout.tsx          # 响应式布局容器
├── hooks/
│   └── useMusicKit.ts      # MusicKit 授权与播放 Hook
└── api/
    └── client.ts           # axios 封装后端 API
```

### 界面风格设计（炫酷现代年轻风）

整体界面遵循 [`requirement.md`](./requirement.md) 中"炫酷的现代年轻风格"定位，设计规范如下：

| 维度 | 规范 | 实现方式 |
| --- | --- | --- |
| 主色调 | 深色系主基调（深空黑 `#0a0a12` / 午夜蓝 `#0f1729`） | Tailwind `bg` 自定义色 / CSS 变量 |
| 点缀色 | 霓虹紫 `#a855f7`、电光蓝 `#3b82f6`、赛博粉 `#ec4899`、辉光青 `#22d3ee` | Tailwind 扩展调色板 |
| 质感 | 毛玻璃 Glassmorphism：半透明 + `backdrop-blur` + 细边框 | Tailwind `backdrop-blur` + `bg-white/5` + `border-white/10` |
| 发光 | 关键元素外发光 | `box-shadow` / `drop-shadow` + 颜色匹配点缀色 |
| 动态背景 | p5.js 粒子随情绪变色流动 | `ParticleBg.tsx` 组件驱动 |
| 渐变流光 | 标题/按钮/雷达描边渐变 | Tailwind `bg-gradient-to-*` + CSS keyframes |
| 字体 | 标题 HarmonyOS Sans / Montserrat 粗体；正文清爽无衬线 | `@font-face` / Google Fonts |
| 图标 | 线性霓虹风 | Phosphor Icons / Lucide |
| 微交互 | 悬停发光放大、入场弹性、点击波纹、切换模糊渐显 | Tailwind `transition` + Framer Motion |
| 可视化 | 雷达图霓虹描边+渐变填充+发光节点；报告用渐变环形/流光折线 | p5.js / ECharts 自定义主题 |

- **深色主题优先**：全站默认深色，天然适配 OLED 省电与夜店氛围；可预留浅色主题切换。
- **情绪联动**：粒子背景与雷达图配色由后端返回的情绪主色调驱动，实现"情绪 → 视觉"的实时映射。
- **移动端降级**：炫酷效果在移动端生效，但降低粒子密度（如桌面 150 粒子 / 移动端 60 粒子）与模糊半径以保帧率。

### 多端适配要点
- 响应式：Tailwind 断点 `sm/md/lg`，移动端单列、桌面多列。
- p5.js：`windowResized` 监听重绘，画布随视口自适应。
- 触控：`touchStarted/touchMoved` 替代鼠标事件。
- iOS Safari：`100dvh` 修复地址栏伸缩；WebAudio 用户交互后 resume；autoplay 需手动触发。
- MusicKit OAuth：移动端用重定向式授权避免弹窗拦截。

---

## 七、部署架构

### Docker 容器编排
```
┌─────────────────────────────────────────┐
│              宿主机                      │
│  ┌──────────┐  ┌──────────┐  ┌───────┐  │
│  │ web 容器  │  │frontend  │  │ db    │  │
│  │ FastAPI  │  │ 静态托管  │  │Postgres│ │
│  │ +Uvicorn │  │ nginx    │  │ :5432 │  │
│  │ :8000    │  │ :80      │  │       │  │
│  └────┬─────┘  └──────────┘  └───┬───┘  │
│       └──── docker network ──────┘      │
│  ┌─────────────────────────────────┐    │
│  │ Volume: pg_data (持久化)         │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### Dockerfile 要点
- 基础镜像 `python:3.11-slim`。
- 系统依赖：`apt-get install ffmpeg libsndfile1`。
- Python 依赖：用 `uv` 安装以复用缓存层，或 `pip install -r requirements.txt`。
- 分层 COPY：先 `pyproject.toml`/`requirements.txt` 再源码，利用缓存。

### docker-compose 服务
- `web`：依赖 `db`，挂载 `.env`，暴露 8000。
- `db`：`postgres:16`，volume 持久化，健康检查。
- `frontend`：nginx 托管前端构建产物，反代 `/api` 到 web。

### 环境变量（.env）
```
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/catte
SECRET_KEY=...
APPLE_MUSIC_KEY_ID=...
APPLE_MUSIC_TEAM_ID=...
APPLE_MUSIC_PRIVATE_KEY_PATH=/run/secrets/authkey.p8
MUSIC_KIT_DEVELOPER_TOKEN=...
```

---

## 八、安全与性能

### 安全
- 密码用 `passlib[bcrypt]` 哈希存储。
- JWT 鉴权，敏感接口需携带 token。
- Apple Music 私钥（.p8）不入库，通过 Docker secrets 挂载。
- 爬虫遵守 robots.txt，控制频率避免封禁。

### 性能
- AI 推理可异步化（RQ + Redis 队列），避免阻塞请求。
- 歌曲情绪结果缓存（Redis 或数据库），避免重复推理。
- p5.js 动画用 `requestAnimationFrame`，移动端降低粒子数量保帧率。
- 数据库索引：`apple_music_id`、`song_id`、`user_id` 外键索引。

---

## 九、Python 环境管理（brew + uv）

- 系统级依赖：`brew install python@3.11 ffmpeg libsndfile postgresql uv`
- 项目依赖：`uv init` / `uv venv --python 3.11` / `uv add ...` / `uv sync`
- 详见 `requirement.md` 中"Python 环境管理方案"小节。

---

*本文档随需求演进持续更新，作为开发与协作的统一参照。*
