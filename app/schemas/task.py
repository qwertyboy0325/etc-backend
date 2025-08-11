"""Task-related Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import TaskPriority, TaskStatus


# Base schemas
class TaskBase(BaseModel):
    """Base task schema with common fields."""

    name: str = Field(..., min_length=1, max_length=200, description="Task name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Task description"
    )
    priority: Optional[TaskPriority] = Field(
        TaskPriority.MEDIUM, description="Task priority"
    )
    max_annotations: Optional[int] = Field(
        3, ge=1, le=10, description="Maximum annotations per task"
    )
    require_review: Optional[bool] = Field(
        True, description="Whether task requires review"
    )
    due_date: Optional[datetime] = Field(None, description="Task due date")
    instructions: Optional[str] = Field(
        None, max_length=2000, description="Special instructions for task"
    )


# Request schemas
class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    pointcloud_file_id: UUID = Field(
        ..., description="Point cloud file ID for this task"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate task name."""
        if not v or not v.strip():
            raise ValueError("Task name cannot be empty")
        return v.strip()

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate due date is in the future."""
        if v and v <= datetime.utcnow():
            raise ValueError("Due date must be in the future")
        return v


class TaskUpdate(BaseModel):
    """Schema for updating an existing task."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: Optional[TaskPriority] = None
    max_annotations: Optional[int] = Field(None, ge=1, le=10)
    require_review: Optional[bool] = None
    due_date: Optional[datetime] = None
    instructions: Optional[str] = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate task name if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError("Task name cannot be empty")
        return v.strip() if v else v

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate due date is in the future."""
        if v and v <= datetime.utcnow():
            raise ValueError("Due date must be in the future")
        return v


class TaskAssignment(BaseModel):
    """Schema for task assignment."""

    assignee_id: UUID = Field(..., description="User ID to assign task to")


class TaskStatusUpdate(BaseModel):
    """Schema for updating task status."""

    status: TaskStatus = Field(..., description="New task status")


# Filter schema
class TaskFilter(BaseModel):
    """Schema for filtering tasks."""

    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assigned_to: Optional[UUID] = None
    created_by: Optional[UUID] = None
    name: Optional[str] = None
    overdue_only: Optional[bool] = False


# Response schemas
class UserSummary(BaseModel):
    """Summary of a user for task responses."""

    id: UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class PointCloudFileSummary(BaseModel):
    """Summary of point cloud file for task responses."""

    id: UUID
    original_filename: str
    file_size: int
    point_count: Optional[int]

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """Full task response schema."""

    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    max_annotations: int
    require_review: bool
    due_date: Optional[datetime]
    instructions: Optional[str]

    # Assignment info
    assigned_to: Optional[UUID]
    assigned_at: Optional[datetime]
    created_by: UUID

    # Point cloud file
    pointcloud_file_id: UUID
    pointcloud_file: Optional[PointCloudFileSummary] = None

    # Completion info
    completed_at: Optional[datetime]
    quality_score: Optional[int]

    # Metadata
    created_at: datetime
    updated_at: datetime

    # Related users
    creator: Optional[UserSummary] = None
    assignee: Optional[UserSummary] = None

    # Computed properties
    is_overdue: bool = False
    is_completed: bool = False
    annotation_count: int = 0
    completion_rate: float = 0.0

    model_config = {"from_attributes": True}

    @field_validator("is_overdue", mode="before")
    @classmethod
    def compute_is_overdue(cls, v, info):
        """Compute if task is overdue."""
        due_date = info.data.get("due_date")
        status = info.data.get("status")
        if not due_date:
            return False
        return due_date < datetime.utcnow() and status not in [
            TaskStatus.COMPLETED,
            TaskStatus.REVIEWED,
            TaskStatus.CANCELLED,
        ]

    @field_validator("is_completed", mode="before")
    @classmethod
    def compute_is_completed(cls, v, info):
        """Compute if task is completed."""
        status = info.data.get("status")
        return status in [TaskStatus.COMPLETED, TaskStatus.REVIEWED]


class TaskSummary(BaseModel):
    """Summary task schema for lists."""

    id: UUID
    name: str
    status: TaskStatus
    priority: TaskPriority
    assigned_to: Optional[UUID]
    assignee: Optional[UserSummary] = None
    due_date: Optional[datetime]
    created_at: datetime
    is_overdue: bool = False
    completion_rate: float = 0.0

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated task list response."""

    items: List[TaskResponse]
    total: int
    page: int
    size: int
    pages: int


class TaskStats(BaseModel):
    """Task statistics schema."""

    total_tasks: int
    pending_tasks: int
    assigned_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    overdue_tasks: int
    completion_rate: float
    status_breakdown: Dict[str, int]


# Notification schemas for task events
class TaskAssignmentNotification(BaseModel):
    """Schema for task assignment notifications."""

    task_id: UUID
    task_name: str
    assignee_id: UUID
    project_id: UUID
    assigned_by: str


class TaskCompletionNotification(BaseModel):
    """Schema for task completion notifications."""

    task_id: UUID
    task_name: str
    project_id: UUID
    completed_by: str
    completion_time: datetime
