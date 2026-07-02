# Catte Music · AI 音乐情绪可视化与探索平台

基于 AI 情绪识别、数据爬虫、Apple Music 集成的全栈音乐探索工具。

## 技术栈

- **后端**：FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL/SQLite
- **AI**：librosa 音频特征提取 + scikit-learn 情绪分类器
- **爬虫**：requests + BeautifulSoup + pycryptodome (JS 逆向)
- **前端**：React + TypeScript + Tailwind CSS + p5.js
- **部署**：Docker + docker-compose
- **环境**：brew + uv (Python) / npm (前端)

## 快速开始

### 1. 后端

```bash
# 系统依赖
brew install python@3.11 ffmpeg libsndfile postgresql uv

# 初始化
cd catte-music
uv venv --python 3.11
source .venv/bin/activate
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 Apple Music 密钥等

# 启动开发服务器
uv run uvicorn app.main:app --reload
```

访问 http://localhost:8000/docs 查看 API 文档。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173。

### 3. Docker 一键部署

```bash
cd docker
docker-compose up --build
```

- 前端：http://localhost
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 项目结构

```
catte-music/
├── app/                 # FastAPI 后端
│   ├── api/             # 路由层
│   ├── models/          # 数据库模型
│   ├── schemas/         # Pydantic 模型
│   ├── services/        # 业务逻辑
│   │   ├── ai/          # AI 引擎(特征提取/分类器/训练)
│   │   ├── crawler/     # 爬虫(反爬/评分/评论)
│   │   └── apple_music/ # Apple Music API 集成
│   └── utils/           # 工具(安全/JWT)
├── frontend/            # React 前端
├── data/                # 爬取数据/模型/音频样本
├── docker/              # Docker 部署
├── tests/               # 测试
└── pyproject.toml       # uv 依赖管理
```

## AI 模型训练

```bash
# 1. 将音频样本按情绪分类放入 data/audio_samples/<情绪名>/
# 2. 训练
python -m app.services.ai.training --data-dir data/audio_samples --output data/models/emotion_model.pkl
```

情绪标签：甜蜜、浪漫、治愈、孤独、悲伤、深情、欢快、愤怒、宁静、热血、忧郁、激昂、松弛、梦幻、震撼

## 参考文档

- [需求文档](../requirement.md)
- [架构文档](../architecture.md)
- [实现计划](../implementation-plan.md)
