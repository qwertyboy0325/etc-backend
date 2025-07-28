"""Point cloud file schemas."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FileStatus


class BoundingBox(BaseModel):
    """Bounding box for point cloud data."""

    min_x: float = Field(..., description="Minimum X coordinate")
    max_x: float = Field(..., description="Maximum X coordinate")
    min_y: float = Field(..., description="Minimum Y coordinate")
    max_y: float = Field(..., description="Maximum Y coordinate")
    min_z: float = Field(..., description="Minimum Z coordinate")
    max_z: float = Field(..., description="Maximum Z coordinate")


class PointCloudFileBase(BaseModel):
    """Base schema for point cloud files."""

    filename: str = Field(..., description="File name in storage")
    original_filename: str = Field(..., description="Original uploaded filename")
    file_size: int = Field(..., description="File size in bytes")
    file_extension: str = Field(..., description="File extension")
    mime_type: Optional[str] = Field(None, description="MIME type")


class PointCloudFileCreate(BaseModel):
    """Schema for creating point cloud files."""

    description: Optional[str] = Field(None, description="File description")


class PointCloudFileUpdate(BaseModel):
    """Schema for updating point cloud files."""

    description: Optional[str] = Field(None, description="File description")


class PointCloudFileResponse(PointCloudFileBase):
    """Schema for point cloud file responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="File ID")
    project_id: UUID = Field(..., description="Project ID")
    status: FileStatus = Field(..., description="File status")
    uploaded_by: UUID = Field(..., description="Uploader user ID")

    # Timestamps
    upload_started_at: datetime = Field(..., description="Upload start time")
    upload_completed_at: Optional[datetime] = Field(
        None, description="Upload completion time"
    )
    processing_started_at: Optional[datetime] = Field(
        None, description="Processing start time"
    )
    processing_completed_at: Optional[datetime] = Field(
        None, description="Processing completion time"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Point cloud metadata
    point_count: Optional[int] = Field(None, description="Number of points")
    dimensions: Optional[int] = Field(None, description="Data dimensions")
    bounding_box: Optional[BoundingBox] = Field(None, description="3D bounding box")

    # Quality metrics
    data_quality: Optional[int] = Field(None, description="Data quality score (1-10)")
    has_noise: bool = Field(False, description="Has noise data")
    has_outliers: bool = Field(False, description="Has outlier points")

    # Additional data
    extra_data: Optional[Dict] = Field(None, description="Additional metadata")

    # Error information
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_details: Optional[Dict] = Field(
        None, description="Detailed error information"
    )

    # File integrity
    checksum: Optional[str] = Field(None, description="SHA-256 checksum")

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB."""
        return self.file_size / (1024 * 1024)

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


class PointCloudFileSummary(BaseModel):
    """Summary schema for point cloud files."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="File ID")
    original_filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    status: FileStatus = Field(..., description="File status")
    point_count: Optional[int] = Field(None, description="Number of points")
    upload_completed_at: Optional[datetime] = Field(
        None, description="Upload completion time"
    )
    created_at: datetime = Field(..., description="Creation timestamp")

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB."""
        return self.file_size / (1024 * 1024)


class PointCloudFileListResponse(BaseModel):
    """Schema for paginated point cloud file lists."""

    items: List[PointCloudFileSummary] = Field(..., description="List of files")
    total: int = Field(..., description="Total number of files")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class FileUploadResponse(BaseModel):
    """Schema for file upload response."""

    file_id: UUID = Field(..., description="Uploaded file ID")
    filename: str = Field(..., description="File name in storage")
    original_filename: str = Field(..., description="Original uploaded filename")
    file_size: int = Field(..., description="File size in bytes")
    status: FileStatus = Field(..., description="Current file status")
    upload_url: Optional[str] = Field(
        None, description="Temporary upload URL if needed"
    )
    point_count: Optional[int] = Field(None, description="Number of points")
    bounding_box: Optional[BoundingBox] = Field(None, description="3D bounding box")
    checksum: str = Field(..., description="File checksum")
    message: str = Field("File uploaded successfully", description="Status message")


class FileDownloadResponse(BaseModel):
    """Schema for file download response."""

    download_url: str = Field(..., description="Temporary download URL")
    expires_at: datetime = Field(..., description="URL expiration time")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")


class PointCloudAnalysis(BaseModel):
    """Schema for point cloud analysis results."""

    point_count: int = Field(..., description="Total number of points")
    dimensions: int = Field(..., description="Data dimensions per point")
    bounding_box: BoundingBox = Field(..., description="3D bounding box")
    has_colors: bool = Field(False, description="Has color information")
    has_normals: bool = Field(False, description="Has normal vectors")
    has_intensity: bool = Field(False, description="Has intensity values")

    # Statistics
    density: Optional[float] = Field(
        None, description="Point density (points per unit volume)"
    )
    coverage_area: Optional[float] = Field(
        None, description="Coverage area (square units)"
    )

    # Quality assessment
    estimated_noise_level: Optional[float] = Field(
        None, description="Estimated noise level"
    )
    outlier_percentage: Optional[float] = Field(
        None, description="Percentage of outlier points"
    )
    uniformity_score: Optional[float] = Field(
        None, description="Point distribution uniformity (0-1)"
    )


class PointCloudPreview(BaseModel):
    """Schema for point cloud preview data."""

    sample_points: List[List[float]] = Field(
        ..., description="Sample points for preview"
    )
    sample_rate: float = Field(..., description="Sampling rate used")
    total_points: int = Field(..., description="Total points in full dataset")
    bounding_box: BoundingBox = Field(..., description="3D bounding box")


class PointCloudStats(BaseModel):
    """Schema for point cloud statistics."""

    total_files: int = Field(..., description="Total number of files")
    total_size: int = Field(..., description="Total size in bytes")
    total_points: int = Field(..., description="Total number of points")

    # Status breakdown
    uploaded_files: int = Field(..., description="Successfully uploaded files")
    processing_files: int = Field(..., description="Files currently processing")
    failed_files: int = Field(..., description="Failed files")

    # File type breakdown
    file_types: Dict[str, int] = Field(..., description="Files by extension")

    # Size statistics
    average_file_size: float = Field(..., description="Average file size in MB")
    largest_file_size: float = Field(..., description="Largest file size in MB")

    @property
    def total_size_mb(self) -> float:
        """Get total size in MB."""
        return self.total_size / (1024 * 1024)

    @property
    def total_size_gb(self) -> float:
        """Get total size in GB."""
        return self.total_size / (1024 * 1024 * 1024)
