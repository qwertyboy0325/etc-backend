"""Annotation-related Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AnnotationStatus, ReviewStatus


# Base schemas
class AnnotationBase(BaseModel):
    """Base annotation schema with common fields."""

    vehicle_type_id: Optional[UUID] = Field(
        None, description="Vehicle type classification"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Annotation confidence score"
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Additional notes for annotation"
    )
    annotation_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional annotation data"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        """Validate confidence is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Confidence must be between 0 and 1")
        return v


# Request schemas
class AnnotationCreate(AnnotationBase):
    """Schema for creating a new annotation."""

    task_id: UUID = Field(..., description="Task ID for this annotation")


class AnnotationUpdate(BaseModel):
    """Schema for updating an existing annotation."""

    vehicle_type_id: Optional[UUID] = Field(
        None, description="Vehicle type classification"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Annotation confidence score"
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Additional notes for annotation"
    )
    annotation_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional annotation data"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        """Validate confidence is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Confidence must be between 0 and 1")
        return v


class AnnotationSubmit(BaseModel):
    """Schema for submitting annotation for review."""

    pass  # No additional fields needed for submission


# Review schemas
class AnnotationReviewCreate(BaseModel):
    """Schema for creating an annotation review."""

    status: ReviewStatus = Field(..., description="Review decision")
    comments: Optional[str] = Field(
        None, max_length=2000, description="Review comments"
    )
    rating: Optional[int] = Field(None, ge=1, le=5, description="Quality rating (1-5)")

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        """Validate rating is between 1 and 5."""
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class AnnotationReviewResponse(BaseModel):
    """Schema for annotation review response."""

    id: UUID
    annotation_id: UUID
    reviewer_id: UUID
    status: ReviewStatus
    comments: Optional[str]
    rating: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Response schemas
class AnnotatorInfo(BaseModel):
    """Schema for annotator information."""

    id: UUID
    full_name: str
    email: str

    class Config:
        from_attributes = True


class TaskInfo(BaseModel):
    """Schema for task information in annotation response."""

    id: UUID
    name: str
    status: str

    class Config:
        from_attributes = True


class VehicleTypeInfo(BaseModel):
    """Schema for vehicle type information."""

    id: UUID
    name: str
    code: str
    description: Optional[str]

    class Config:
        from_attributes = True


class AnnotationResponse(BaseModel):
    """Schema for annotation response."""

    id: UUID
    task_id: UUID
    annotator_id: UUID
    vehicle_type_id: Optional[UUID]
    vehicle_type_name: Optional[str]
    confidence: Optional[float]
    notes: Optional[str]
    status: AnnotationStatus
    started_at: datetime
    submitted_at: Optional[datetime]
    time_spent: Optional[int]
    quality_score: Optional[int]
    extra_data: Optional[Dict[str, Any]]
    version: int
    created_at: datetime
    updated_at: datetime

    # Related objects
    annotator: Optional[AnnotatorInfo] = None
    task: Optional[TaskInfo] = None
    vehicle_type: Optional[VehicleTypeInfo] = None
    reviews: Optional[List[AnnotationReviewResponse]] = []

    class Config:
        from_attributes = True


class AnnotationListResponse(BaseModel):
    """Schema for annotation list response with pagination."""

    items: List[AnnotationResponse]
    total: int
    page: int
    size: int
    pages: int


class AnnotationSummary(BaseModel):
    """Schema for annotation summary."""

    id: UUID
    task_id: UUID
    vehicle_type_name: Optional[str]
    confidence: Optional[float]
    status: AnnotationStatus
    annotator_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnnotationStats(BaseModel):
    """Schema for annotation statistics."""

    status_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count by status"
    )
    average_confidence: float = Field(0.0, description="Average confidence score")
    total_annotations: int = Field(0, description="Total number of annotations")
    completion_rate: Optional[float] = Field(
        None, description="Completion rate percentage"
    )


# Bulk operations
class BulkAnnotationReview(BaseModel):
    """Schema for bulk annotation review."""

    annotation_ids: List[UUID] = Field(
        ..., min_length=1, description="List of annotation IDs to review"
    )
    status: ReviewStatus = Field(..., description="Review decision for all annotations")
    comments: Optional[str] = Field(
        None, max_length=2000, description="Comments for all annotations"
    )

    @field_validator("annotation_ids")
    @classmethod
    def validate_annotation_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate annotation IDs list is not empty."""
        if not v:
            raise ValueError("At least one annotation ID is required")
        return v


class BulkAnnotationReviewResponse(BaseModel):
    """Schema for bulk annotation review response."""

    success_count: int = Field(
        ..., description="Number of successfully reviewed annotations"
    )
    failed_count: int = Field(0, description="Number of failed reviews")
    failed_ids: List[UUID] = Field(
        default_factory=list, description="IDs of failed reviews"
    )
    errors: List[str] = Field(default_factory=list, description="Error messages")


# Filter and query schemas
class AnnotationFilter(BaseModel):
    """Schema for annotation filtering and querying."""

    status: Optional[AnnotationStatus] = Field(
        None, description="Filter by annotation status"
    )
    annotator_id: Optional[UUID] = Field(None, description="Filter by annotator")
    vehicle_type_id: Optional[UUID] = Field(None, description="Filter by vehicle type")
    min_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Minimum confidence score"
    )
    max_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Maximum confidence score"
    )
    start_date: Optional[datetime] = Field(
        None, description="Filter annotations created after this date"
    )
    end_date: Optional[datetime] = Field(
        None, description="Filter annotations created before this date"
    )
    task_ids: Optional[List[UUID]] = Field(
        None, description="Filter by specific task IDs"
    )

    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Items per page")

    @field_validator("min_confidence", "max_confidence")
    @classmethod
    def validate_confidence_range(cls, v: Optional[float]) -> Optional[float]:
        """Validate confidence is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Confidence must be between 0 and 1")
        return v

    def model_post_init(self, __context) -> None:
        """Validate confidence range after model initialization."""
        if (
            self.min_confidence is not None
            and self.max_confidence is not None
            and self.min_confidence > self.max_confidence
        ):
            raise ValueError("min_confidence cannot be greater than max_confidence")

        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date cannot be greater than end_date")


# Export schema for annotations
class AnnotationExport(BaseModel):
    """Schema for exporting annotations."""

    annotation_id: UUID
    task_name: str
    annotator_name: str
    vehicle_type_name: Optional[str]
    confidence: Optional[float]
    notes: Optional[str]
    status: AnnotationStatus
    created_at: datetime
    submitted_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    annotation_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True
