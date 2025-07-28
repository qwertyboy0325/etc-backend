"""File upload service for point cloud data."""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Dict, Optional
from uuid import UUID, uuid4

import numpy as np
from fastapi import HTTPException, UploadFile, status
from minio import Minio
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.enums import FileStatus
from app.models.pointcloud import PointCloudFile
from app.models.project import Project


class FileUploadService:
    """Service for handling point cloud file uploads."""

    def __init__(self, db: AsyncSession):
        """Initialize file upload service."""
        self.db = db
        self.allowed_extensions = {".npy", ".npz", ".ply", ".pcd"}
        self.max_file_size = settings.MAX_FILE_SIZE * 1024 * 1024  # Convert MB to bytes

        # Initialize MinIO client
        self.minio_client = Minio(
            endpoint=f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )

        # Ensure bucket exists
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Ensure the MinIO bucket exists."""
        try:
            if not self.minio_client.bucket_exists(settings.MINIO_BUCKET):
                self.minio_client.make_bucket(settings.MINIO_BUCKET)
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create storage bucket: {e}",
            )

    def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
            )

        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(self.allowed_extensions)}",
            )

        # Check file size (if available)
        if hasattr(file, "size") and file.size and file.size > self.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE}MB",
            )

    def _calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA-256 checksum of file content."""
        return hashlib.sha256(content).hexdigest()

    def _get_storage_path(self, project_id: UUID, filename: str) -> str:
        """Generate storage path for the file."""
        file_ext = Path(filename).suffix.lower()
        unique_filename = f"{uuid4()}{file_ext}"
        return f"projects/{project_id}/pointclouds/{unique_filename}"

    async def _save_to_storage(self, content: bytes, storage_path: str) -> None:
        """Save file content to MinIO storage."""
        try:
            # Create a temporary file-like object from bytes
            from io import BytesIO

            file_data = BytesIO(content)

            self.minio_client.put_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=storage_path,
                data=file_data,
                length=len(content),
                content_type="application/octet-stream",
            )
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file to storage: {e}",
            )

    async def _analyze_point_cloud(self, content: bytes, file_extension: str) -> Dict:
        """Analyze point cloud file and extract metadata."""
        try:
            from io import BytesIO

            if file_extension == ".npy":
                data = np.load(BytesIO(content))
            elif file_extension == ".npz":
                npz_data = np.load(BytesIO(content))
                # Take the first array if multiple arrays exist
                data = npz_data[list(npz_data.keys())[0]]
            else:
                # For other formats, return basic info
                return {
                    "point_count": None,
                    "dimensions": None,
                    "bounding_box": None,
                    "has_colors": False,
                    "has_normals": False,
                }

            # Basic validation
            if data.ndim != 2:
                raise ValueError("Point cloud data must be 2D array")

            point_count, dimensions = data.shape

            # Calculate bounding box (assuming first 3 columns are x, y, z)
            xyz_data = data[:, :3] if dimensions >= 3 else data
            bounding_box = {
                "min_x": float(xyz_data[:, 0].min()),
                "max_x": float(xyz_data[:, 0].max()),
                "min_y": float(xyz_data[:, 1].min()) if xyz_data.shape[1] > 1 else 0.0,
                "max_y": float(xyz_data[:, 1].max()) if xyz_data.shape[1] > 1 else 0.0,
                "min_z": float(xyz_data[:, 2].min()) if xyz_data.shape[1] > 2 else 0.0,
                "max_z": float(xyz_data[:, 2].max()) if xyz_data.shape[1] > 2 else 0.0,
            }

            return {
                "point_count": int(point_count),
                "dimensions": int(dimensions),
                "bounding_box": bounding_box,
                "has_colors": dimensions > 3,
                "has_normals": dimensions > 6,
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to analyze point cloud data: {e}",
            )

    async def upload_pointcloud(
        self,
        file: UploadFile,
        project_id: UUID,
        uploaded_by: UUID,
        description: Optional[str] = None,
    ) -> PointCloudFile:
        """
        Upload a point cloud file.

        Args:
            file: The uploaded file
            project_id: Project ID to associate with the file
            uploaded_by: User ID who uploaded the file
            description: Optional file description

        Returns:
            PointCloudFile: The created file record
        """
        # Validate inputs
        self._validate_file(file)

        # Read file content
        content = await file.read()
        if len(content) > self.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE}MB",
            )

        # Calculate checksum
        checksum = self._calculate_checksum(content)

        # Check for duplicate files in the same project
        # (Optional: you might want to allow duplicates)

        # Generate storage path
        storage_path = self._get_storage_path(project_id, file.filename)
        file_ext = Path(file.filename).suffix.lower()

        # Create file record in database
        pointcloud_file = PointCloudFile(
            project_id=project_id,
            filename=Path(storage_path).name,
            original_filename=file.filename,
            file_path=storage_path,
            file_size=len(content),
            file_extension=file_ext,
            mime_type=file.content_type,
            uploaded_by=uploaded_by,
            checksum=checksum,
            status=FileStatus.UPLOADING,
            upload_started_at=datetime.utcnow(),
        )

        try:
            # Save to database first
            self.db.add(pointcloud_file)
            await self.db.commit()
            await self.db.refresh(pointcloud_file)

            # Save to storage
            await self._save_to_storage(content, storage_path)

            # Analyze point cloud data
            analysis_result = await self._analyze_point_cloud(content, file_ext)

            # Update file record with analysis results
            pointcloud_file.mark_upload_completed()
            pointcloud_file.set_point_cloud_metadata(
                point_count=analysis_result["point_count"],
                dimensions=analysis_result["dimensions"],
                bounding_box=analysis_result["bounding_box"],
            )

            await self.db.commit()
            await self.db.refresh(pointcloud_file)

            return pointcloud_file

        except Exception as e:
            # Rollback database changes
            await self.db.rollback()

            # Try to clean up storage
            try:
                self.minio_client.remove_object(settings.MINIO_BUCKET, storage_path)
            except:
                pass  # Ignore cleanup errors

            # Mark as failed if record exists
            if pointcloud_file.id:
                pointcloud_file.mark_processing_failed(str(e))
                await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {e}",
            )

    async def get_file_by_id(self, file_id: UUID) -> Optional[PointCloudFile]:
        """Get point cloud file by ID."""
        from sqlalchemy import select

        stmt = select(PointCloudFile).where(PointCloudFile.id == file_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_project_files(
        self,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[FileStatus] = None,
    ) -> list[PointCloudFile]:
        """Get point cloud files for a project."""
        from sqlalchemy import select

        stmt = select(PointCloudFile).where(PointCloudFile.project_id == project_id)

        if status_filter:
            stmt = stmt.where(PointCloudFile.status == status_filter)

        stmt = stmt.offset(skip).limit(limit).order_by(PointCloudFile.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_file(self, file_id: UUID, deleted_by: UUID) -> bool:
        """
        Delete a point cloud file.

        Args:
            file_id: File ID to delete
            deleted_by: User ID who is deleting the file

        Returns:
            bool: True if deleted successfully
        """
        file_record = await self.get_file_by_id(file_id)
        if not file_record:
            return False

        try:
            # Remove from storage
            self.minio_client.remove_object(
                settings.MINIO_BUCKET, file_record.file_path
            )

            # Mark as deleted in database (soft delete)
            file_record.mark_deleted()
            await self.db.commit()

            return True

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file: {e}",
            )

    async def get_download_url(self, file_id: UUID, expires_in_hours: int = 1) -> str:
        """
        Generate a temporary download URL for a file.

        Args:
            file_id: File ID
            expires_in_hours: URL expiration time in hours

        Returns:
            str: Temporary download URL
        """
        file_record = await self.get_file_by_id(file_id)
        if not file_record or file_record.status == FileStatus.DELETED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        try:
            from datetime import timedelta

            url = self.minio_client.presigned_get_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=file_record.file_path,
                expires=timedelta(hours=expires_in_hours),
            )
            return url

        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate download URL: {e}",
            )
