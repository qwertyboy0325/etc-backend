"""
文件管理 API 端點
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User

router = APIRouter()


class FileInfo(BaseModel):
    """文件信息模型"""

    id: str
    original_filename: str
    file_size: int
    status: str
    point_count: Optional[int] = None
    dimensions: Optional[int] = None
    min_x: Optional[str] = None
    max_x: Optional[str] = None
    min_y: Optional[str] = None
    max_y: Optional[str] = None
    min_z: Optional[str] = None
    max_z: Optional[str] = None
    upload_completed_at: Optional[str] = None
    created_at: str


@router.get("/files", response_model=List[FileInfo])
async def list_files(current_user: User = Depends(get_current_user)):
    """
    獲取文件列表
    """
    try:
        uploads_dir = Path("uploads")
        if not uploads_dir.exists():
            return []

        files = []
        for file_path in uploads_dir.glob("*.npy"):
            # 獲取文件信息
            stat = file_path.stat()

            # 簡單的點雲信息估算
            point_count = int(stat.st_size / 12)  # 假設每個點3個float32 (12 bytes)

            files.append(
                FileInfo(
                    id=file_path.stem,
                    original_filename=file_path.name,
                    file_size=stat.st_size,
                    status="UPLOADED",
                    point_count=point_count,
                    dimensions=3,
                    min_x="-50.0",
                    max_x="50.0",
                    min_y="-50.0",
                    max_y="50.0",
                    min_z="-50.0",
                    max_z="50.0",
                    upload_completed_at=datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(),
                    created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                )
            )

        return files

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/files/{file_id}/download")
async def download_file(file_id: str, current_user: User = Depends(get_current_user)):
    """
    下載文件
    """
    try:
        uploads_dir = Path("uploads")
        file_path = uploads_dir / f"{file_id}.npy"

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download file: {str(e)}"
        )


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...), current_user: User = Depends(get_current_user)
):
    """
    上傳文件
    """
    try:
        # 檢查文件類型
        if not file.filename.endswith(".npy"):
            raise HTTPException(status_code=400, detail="Only .npy files are allowed")

        # 創建uploads目錄
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)

        # 保存文件
        file_path = uploads_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 獲取文件信息
        stat = file_path.stat()
        point_count = int(stat.st_size / 12)

        return FileInfo(
            id=file_path.stem,
            original_filename=file_path.name,
            file_size=stat.st_size,
            status="UPLOADED",
            point_count=point_count,
            dimensions=3,
            min_x="-50.0",
            max_x="50.0",
            min_y="-50.0",
            max_y="50.0",
            min_z="-50.0",
            max_z="50.0",
            upload_completed_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
