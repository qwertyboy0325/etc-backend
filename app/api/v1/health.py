"""
健康檢查和系統狀態 API 端點
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np
import psutil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
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
    基礎健康檢查端點，包含數據庫連接檢查
    """
    from app.core.database import check_db_health

    # 檢查數據庫連接
    db_healthy = await check_db_health()

    if not db_healthy:
        raise HTTPException(
            status_code=503, detail="Database connection failed - system is unhealthy"
        )

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
    簡單的 ping 端點，用於測試服務是否運行
    """
    return {"message": "pong", "timestamp": datetime.utcnow()}


@router.get("/generate-sample-npy")
async def generate_sample_npy():
    """
    生成示例npy文件供測試使用
    """
    try:
        # 創建uploads目錄（如果不存在）
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)

        # 生成不同類型的示例點雲數據
        sample_files = []

        # 1. 球狀分布的點雲
        sphere_points = 5000
        radius = 50
        theta = np.random.uniform(0, 2 * np.pi, sphere_points)
        phi = np.random.uniform(0, np.pi, sphere_points)
        r = np.random.uniform(0, radius, sphere_points)

        x_sphere = r * np.sin(phi) * np.cos(theta)
        y_sphere = r * np.sin(phi) * np.sin(theta)
        z_sphere = r * np.cos(phi)

        sphere_data = np.column_stack([x_sphere, y_sphere, z_sphere]).astype(np.float32)
        sphere_file = uploads_dir / "sphere_sample.npy"
        np.save(sphere_file, sphere_data)
        sample_files.append(str(sphere_file))

        # 2. 立方體分布的點雲
        cube_points = 3000
        cube_data = np.random.uniform(-30, 30, (cube_points, 3)).astype(np.float32)
        cube_file = uploads_dir / "cube_sample.npy"
        np.save(cube_file, cube_data)
        sample_files.append(str(cube_file))

        # 3. 圓柱體分布的點雲
        cylinder_points = 4000
        radius_cyl = 20
        height = 60

        theta_cyl = np.random.uniform(0, 2 * np.pi, cylinder_points)
        z_cyl = np.random.uniform(-height / 2, height / 2, cylinder_points)
        r_cyl = np.random.uniform(0, radius_cyl, cylinder_points)

        x_cyl = r_cyl * np.cos(theta_cyl)
        y_cyl = r_cyl * np.sin(theta_cyl)

        cylinder_data = np.column_stack([x_cyl, y_cyl, z_cyl]).astype(np.float32)
        cylinder_file = uploads_dir / "cylinder_sample.npy"
        np.save(cylinder_file, cylinder_data)
        sample_files.append(str(cylinder_file))

        # 4. 車輛形狀的點雲（簡化版）
        car_points = 6000
        # 車身（長方體）
        body_points = int(car_points * 0.7)
        x_body = np.random.uniform(-25, 25, body_points)
        y_body = np.random.uniform(-10, 10, body_points)
        z_body = np.random.uniform(0, 8, body_points)

        # 車輪（圓柱體）
        wheel_points = car_points - body_points
        wheel_radius = 8
        wheel_height = 4

        theta_wheel = np.random.uniform(0, 2 * np.pi, wheel_points)
        z_wheel = np.random.uniform(0, wheel_height, wheel_points)
        r_wheel = np.random.uniform(0, wheel_radius, wheel_points)

        x_wheel = r_wheel * np.cos(theta_wheel) + np.random.choice(
            [-20, 20], wheel_points
        )
        y_wheel = r_wheel * np.sin(theta_wheel)

        car_data = np.vstack(
            [
                np.column_stack([x_body, y_body, z_body]),
                np.column_stack([x_wheel, y_wheel, z_wheel]),
            ]
        ).astype(np.float32)

        car_file = uploads_dir / "car_sample.npy"
        np.save(car_file, car_data)
        sample_files.append(str(car_file))

        return {
            "message": "Sample NPY files generated successfully",
            "files": sample_files,
            "total_files": len(sample_files),
            "upload_dir": str(uploads_dir.absolute()),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate sample files: {str(e)}"
        )


@router.get("/download-sample/{filename}")
async def download_sample_file(filename: str):
    """
    下載生成的示例npy文件
    """
    try:
        file_path = Path("uploads") / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/octet-stream",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download file: {str(e)}"
        )
