"""Point cloud file model definitions."""

from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from app.models.base import BaseProjectModel
from app.models.enums import FileStatus


class PointCloudFile(BaseProjectModel):
    """Point cloud file model for storing file metadata and processing status."""

    __tablename__ = "pointcloud_files"

    # Basic Information
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Path in storage

    # File Properties
    file_size = Column(BigInteger, nullable=False)  # Size in bytes
    file_extension = Column(String(10), nullable=False)  # .npy, .npz
    mime_type = Column(String(100), nullable=True)

    # Status
    status = Column(
        Enum(FileStatus), default=FileStatus.UPLOADING, nullable=False, index=True
    )

    # Upload Information
    uploaded_by = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    upload_started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    upload_completed_at = Column(DateTime, nullable=True)

    # Processing Information
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processing_logs = Column(Text, nullable=True)

    # Point Cloud Metadata
    point_count = Column(Integer, nullable=True)
    dimensions = Column(Integer, nullable=True)  # Usually 3 for x,y,z

    # Bounding Box
    min_x = Column(
        String(50), nullable=True
    )  # Using string to avoid float precision issues
    max_x = Column(String(50), nullable=True)
    min_y = Column(String(50), nullable=True)
    max_y = Column(String(50), nullable=True)
    min_z = Column(String(50), nullable=True)
    max_z = Column(String(50), nullable=True)

    # Quality Metrics
    data_quality = Column(Integer, nullable=True)  # 1-10 scale
    has_noise = Column(Boolean, default=False, nullable=False)
    has_outliers = Column(Boolean, default=False, nullable=False)

    # Additional Data
    extra_data = Column(JSON, nullable=True)  # Additional file metadata

    # Error Information
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Checksum for integrity
    checksum = Column(String(64), nullable=True)  # SHA-256

    # Relationships
    project = relationship("Project", back_populates="pointcloud_files")

    uploader = relationship("User", foreign_keys=[uploaded_by])

    tasks = relationship(
        "Task", back_populates="pointcloud_file", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PointCloudFile(id={self.id}, filename='{self.filename}', status='{self.status}')>"

    @property
    def is_uploaded(self) -> bool:
        """Check if file has been uploaded successfully."""
        return self.status in [
            FileStatus.UPLOADED,
            FileStatus.PROCESSING,
            FileStatus.PROCESSED,
        ]

    @property
    def is_processing(self) -> bool:
        """Check if file is currently being processed."""
        return self.status == FileStatus.PROCESSING

    @property
    def is_processed(self) -> bool:
        """Check if file has been processed successfully."""
        return self.status == FileStatus.PROCESSED

    @property
    def is_failed(self) -> bool:
        """Check if file processing failed."""
        return self.status == FileStatus.FAILED

    @property
    def is_deleted(self) -> bool:
        """Check if file has been deleted."""
        return self.status == FileStatus.DELETED

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB."""
        return self.file_size / (1024 * 1024)

    @property
    def upload_duration(self) -> Optional[float]:
        """Calculate upload duration in seconds."""
        if not self.upload_completed_at:
            return None

        time_diff = self.upload_completed_at - self.upload_started_at
        return time_diff.total_seconds()

    @property
    def processing_duration(self) -> Optional[float]:
        """Calculate processing duration in seconds."""
        if not self.processing_started_at or not self.processing_completed_at:
            return None

        time_diff = self.processing_completed_at - self.processing_started_at
        return time_diff.total_seconds()

    @property
    def bounding_box(self) -> Optional[Dict[str, float]]:
        """Get bounding box as a dictionary."""
        if not all(
            [self.min_x, self.max_x, self.min_y, self.max_y, self.min_z, self.max_z]
        ):
            return None

        return {
            "min_x": float(self.min_x),
            "max_x": float(self.max_x),
            "min_y": float(self.min_y),
            "max_y": float(self.max_y),
            "min_z": float(self.min_z),
            "max_z": float(self.max_z),
        }

    def mark_upload_completed(self) -> None:
        """Mark file upload as completed."""
        self.upload_completed_at = datetime.utcnow()
        self.status = FileStatus.UPLOADED

    def mark_processing_started(self) -> None:
        """Mark file processing as started."""
        self.processing_started_at = datetime.utcnow()
        self.status = FileStatus.PROCESSING

    def mark_processing_completed(self) -> None:
        """Mark file processing as completed."""
        self.processing_completed_at = datetime.utcnow()
        self.status = FileStatus.PROCESSED

    def mark_processing_failed(
        self, error_message: str, error_details: Optional[Dict] = None
    ) -> None:
        """Mark file processing as failed."""
        self.status = FileStatus.FAILED
        self.error_message = error_message
        self.error_details = error_details

    def mark_deleted(self) -> None:
        """Mark file as deleted."""
        self.status = FileStatus.DELETED

    def set_point_cloud_metadata(
        self,
        point_count: int,
        dimensions: int,
        bounding_box: Optional[Dict[str, float]] = None,
    ) -> None:
        """Set point cloud metadata."""
        self.point_count = point_count
        self.dimensions = dimensions

        if bounding_box:
            self.min_x = str(bounding_box["min_x"])
            self.max_x = str(bounding_box["max_x"])
            self.min_y = str(bounding_box["min_y"])
            self.max_y = str(bounding_box["max_y"])
            self.min_z = str(bounding_box["min_z"])
            self.max_z = str(bounding_box["max_z"])

    def can_create_tasks(self) -> bool:
        """Check if tasks can be created for this file."""
        return (
            self.status == FileStatus.PROCESSED
            and self.point_count
            and self.point_count > 0
        )

    def get_task_count(self) -> int:
        """Get number of tasks created for this file."""
        return len(self.tasks)

    def get_completed_task_count(self) -> int:
        """Get number of completed tasks for this file."""
        from app.models.enums import TaskStatus

        return len([t for t in self.tasks if t.status == TaskStatus.COMPLETED])

    @property
    def task_completion_rate(self) -> float:
        """Calculate task completion rate for this file."""
        total_tasks = self.get_task_count()
        if total_tasks == 0:
            return 0.0

        completed_tasks = self.get_completed_task_count()
        return (completed_tasks / total_tasks) * 100
