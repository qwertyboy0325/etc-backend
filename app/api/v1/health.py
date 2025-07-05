"""
健康檢查和系統狀態 API 端點
"""
import asyncio
from datetime import datetime
from typing import Any, Dict

import psutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.annotation import Annotation
from app.models.project import Project
from app.models.task import Task
from app.models.user import User

router = APIRouter()


class HealthResponse(BaseModel):
    """健康檢查響應模型"""

    status: str = "ok"
    timestamp: datetime
    version: str = "1.0.0"
    message: str = "ETC Point Cloud Annotation System is running"


class DatabaseStatus(BaseModel):
    """數據庫狀態模型"""

    connected: bool
    response_time_ms: float
    tables_count: int
    last_check: datetime


class SystemInfo(BaseModel):
    """系統信息模型"""

    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: str
    python_version: str
    database_status: DatabaseStatus


class ModelValidation(BaseModel):
    """模型驗證結果"""

    models_validated: int
    tables_created: int
    relationships_valid: bool
    validation_details: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    基礎健康檢查端點
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        message="ETC Point Cloud Annotation System is running",
    )


@router.get("/database/status", response_model=DatabaseStatus)
async def database_status(db: AsyncSession = Depends(get_db)):
    """
    數據庫連接狀態檢查
    """
    try:
        start_time = datetime.utcnow()

        # 執行簡單查詢測試連接
        result = await db.execute(text("SELECT 1"))
        result.fetchone()

        # 計算響應時間
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # 查詢表數量
        tables_result = await db.execute(
            text(
                """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """
            )
        )
        tables_count = tables_result.scalar()

        return DatabaseStatus(
            connected=True,
            response_time_ms=round(response_time, 2),
            tables_count=tables_count,
            last_check=datetime.utcnow(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Database connection failed: {str(e)}"
        )


@router.get("/models/validate", response_model=ModelValidation)
async def validate_models(db: AsyncSession = Depends(get_db)):
    """
    驗證數據模型結構
    """
    try:
        models_to_validate = [
            ("users", User),
            ("projects", Project),
            ("tasks", Task),
            ("annotations", Annotation),
        ]

        validation_details = {}
        models_validated = 0
        tables_created = 0

        for table_name, model_class in models_to_validate:
            try:
                # 檢查表是否存在
                table_check = await db.execute(
                    text(
                        f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = '{table_name}'
                    )
                """
                    )
                )
                table_exists = table_check.scalar()

                if table_exists:
                    tables_created += 1

                    # 驗證模型結構
                    sample_query = await db.execute(
                        text(f"SELECT * FROM {table_name} LIMIT 1")
                    )
                    columns = list(sample_query.keys()) if sample_query.keys() else []

                    validation_details[table_name] = {
                        "exists": True,
                        "columns_count": len(columns),
                        "model_class": model_class.__name__,
                    }
                    models_validated += 1
                else:
                    validation_details[table_name] = {
                        "exists": False,
                        "error": "Table not found",
                    }

            except Exception as e:
                validation_details[table_name] = {"exists": False, "error": str(e)}

        return ModelValidation(
            models_validated=models_validated,
            tables_created=tables_created,
            relationships_valid=models_validated > 0,
            validation_details=validation_details,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Model validation failed: {str(e)}"
        )


@router.get("/info", response_model=SystemInfo)
async def system_info(db: AsyncSession = Depends(get_db)):
    """
    系統信息端點
    """
    try:
        # 獲取系統資源使用情況
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # 獲取數據庫狀態
        db_status = await database_status(db)

        # 計算系統運行時間
        import platform

        return SystemInfo(
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            uptime=f"{psutil.boot_time():.0f}",
            python_version=platform.python_version(),
            database_status=db_status,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"System info retrieval failed: {str(e)}"
        )


@router.get("/ping")
async def ping():
    """
    簡單的 ping 端點
    """
    return {"message": "pong", "timestamp": datetime.utcnow()}
