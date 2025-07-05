# ETC Point Cloud Annotation System - Backend

FastAPI 後端服務，提供點雲標注系統的 API 服務。

## 技術棧

- **Python 3.11** - 程式語言
- **FastAPI** - Web 框架
- **PostgreSQL** - 主資料庫
- **Redis** - 緩存和消息佇列
- **MinIO** - 對象存儲
- **Celery** - 異步任務處理
- **SQLAlchemy** - ORM
- **Alembic** - 資料庫遷移
- **Docker** - 容器化部署

## 專案結構

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 應用入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 資料庫連接
│   │   ├── security.py        # 認證安全
│   │   └── exceptions.py      # 異常處理
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py        # 認證 API
│   │       ├── projects.py    # 專案 API
│   │       ├── tasks.py       # 任務 API
│   │       ├── annotations.py # 標注 API
│   │       └── users.py       # 用戶 API
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py           # 用戶模型
│   │   ├── project.py        # 專案模型
│   │   ├── task.py           # 任務模型
│   │   └── annotation.py     # 標注模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py           # 認證服務
│   │   ├── project.py        # 專案服務
│   │   ├── task.py           # 任務服務
│   │   └── file_storage.py   # 文件存儲服務
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py           # 用戶 Pydantic 模型
│   │   ├── project.py        # 專案 Pydantic 模型
│   │   └── task.py           # 任務 Pydantic 模型
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py        # 工具函數
│       └── constants.py      # 常數定義
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_projects.py
│   └── conftest.py
├── migrations/                # Alembic 遷移文件
├── requirements.txt
├── pyproject.toml            # Python 專案配置
├── env.example               # 環境變數範例
├── .pre-commit-config.yaml   # Pre-commit 配置
├── Dockerfile.dev            # 開發環境 Dockerfile
├── Dockerfile.prod           # 生產環境 Dockerfile
└── README.md
```

## 快速開始

### 1. 環境需求

- Python 3.11+
- Docker & Docker Compose
- Git

### 2. 克隆專案

```bash
git clone <repository-url>
cd ETC/backend
```

### 3. 環境配置

```bash
# 複製環境變數範例
cp env.example .env

# 編輯環境變數（可選，預設值已可用於開發）
vim .env
```

### 4. 使用 Docker 運行（推薦）

```bash
# 回到專案根目錄
cd ..

# 啟動所有服務
docker-compose -f docker-compose.dev.yml up -d

# 查看服務狀態
docker-compose -f docker-compose.dev.yml ps

# 查看 API 日誌
docker-compose -f docker-compose.dev.yml logs -f api
```

### 5. 訪問服務

- **API 文檔**: <http://localhost:8000/api/v1/docs>
- **API 根路徑**: <http://localhost:8000/>
- **健康檢查**: <http://localhost:8000/health>
- **MinIO 控制台**: <http://localhost:9001> (minioadmin/minioadmin)
- **Celery Flower**: <http://localhost:5555>

### 6. 本地開發（不使用 Docker）

```bash
# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安裝依賴
pip install -r requirements.txt

# 安裝 pre-commit hooks
pre-commit install

# 確保 PostgreSQL, Redis, MinIO 運行
# 可以使用 docker-compose 僅啟動依賴服務：
docker-compose -f docker-compose.dev.yml up -d db redis minio

# 運行開發服務器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 開發指南

### 代碼風格

專案使用 Google Python Style Guide 和以下工具：

```bash
# 格式化代碼
black .
isort .

# 檢查代碼
flake8 .
mypy .

# 運行所有檢查
pre-commit run --all-files
```

### 測試

```bash
# 運行所有測試
pytest

# 運行特定測試文件
pytest tests/test_auth.py

# 運行測試並生成覆蓋率報告
pytest --cov=app --cov-report=html
```

### 資料庫遷移

```bash
# 進入 API 容器
docker-compose -f docker-compose.dev.yml exec api bash

# 初始化 Alembic（僅第一次）
alembic init migrations

# 創建新的遷移
alembic revision --autogenerate -m "Add user table"

# 執行遷移
alembic upgrade head

# 查看遷移歷史
alembic history
```

### 添加新功能

1. **創建模型** (models/)
2. **創建 Pydantic 模式** (schemas/)
3. **創建服務層** (services/)
4. **創建 API 路由** (api/v1/)
5. **寫測試** (tests/)
6. **更新文檔**

### 環境變數說明

主要環境變數：

```bash
# 應用配置
APP_NAME=ETC Point Cloud Annotation System
DEBUG=True
ENVIRONMENT=development

# 資料庫配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etc_pointcloud_dev
DB_USER=root
DB_PASSWORD=root

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO 配置
MINIO_HOST=localhost
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# JWT 配置
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

詳細配置請參考 `env.example` 文件。

## API 文檔

API 文檔在開發模式下自動生成：

- **Swagger UI**: <http://localhost:8000/api/v1/docs>
- **ReDoc**: <http://localhost:8000/api/v1/redoc>
- **OpenAPI JSON**: <http://localhost:8000/api/v1/openapi.json>

## 部署

### 開發環境部署

```bash
# 啟動開發環境
docker-compose -f docker-compose.dev.yml up -d
```

### 生產環境部署

```bash
# 建構生產映像
docker build -f Dockerfile.prod -t etc-backend:prod .

# 使用生產配置
docker-compose -f docker-compose.prod.yml up -d
```

## 監控和日誌

### 日誌查看

```bash
# 查看 API 日誌
docker-compose -f docker-compose.dev.yml logs -f api

# 查看資料庫日誌
docker-compose -f docker-compose.dev.yml logs -f db

# 查看 Redis 日誌
docker-compose -f docker-compose.dev.yml logs -f redis
```

### Celery 監控

Celery Flower 提供任務監控：<http://localhost:5555>

### 健康檢查

```bash
# 簡單健康檢查
curl http://localhost:8000/health

# 詳細健康檢查（包含資料庫）
curl http://localhost:8000/api/v1/health
```

## 故障排除

### 常見問題

1. **容器無法啟動**

   ```bash
   # 檢查 Docker 狀態
   docker ps

   # 查看容器日誌
   docker-compose logs [service-name]

   # 重建容器
   docker-compose down && docker-compose up --build
   ```

2. **資料庫連接失敗**

   ```bash
   # 檢查資料庫容器
   docker-compose exec db psql -U root -d etc_pointcloud_dev

   # 重置資料庫
   docker-compose down -v && docker-compose up -d
   ```

3. **依賴問題**

   ```bash
   # 重新建構映像
   docker-compose build --no-cache

   # 清理舊映像
   docker system prune -a
   ```

### 開發工具

- **資料庫**: 使用 DBeaver 或 pgAdmin 連接 PostgreSQL
- **API 測試**: 使用 Postman 或 curl
- **Redis**: 使用 Redis CLI 或 RedisInsight

## 貢獻指南

1. Fork 專案
2. 創建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 創建 Pull Request

## 授權

本專案採用 MIT 授權 - 詳見 [LICENSE](LICENSE) 文件。

## 支援

如有問題請聯繫：

- 郵件：<dev@etc.com>
- 問題追蹤：[GitHub Issues](https://github.com/etc/pointcloud/issues)
