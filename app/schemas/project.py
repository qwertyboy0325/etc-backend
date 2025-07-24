"""Project schemas for API requests and responses."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublic


class ProjectBase(BaseModel):
    """Base project schema with common fields."""

    name: str = Field(..., min_length=2, max_length=200, description="Project name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description"
    )
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date")


class ProjectCreate(ProjectBase):
    """Schema for project creation."""

    is_public: bool = Field(False, description="Whether project is public")
    max_annotations_per_task: int = Field(
        3, ge=1, le=10, description="Maximum annotations per task"
    )
    auto_assign_tasks: bool = Field(
        True, description="Enable automatic task assignment"
    )
    require_review: bool = Field(True, description="Require review for annotations")


class ProjectUpdate(BaseModel):
    """Schema for project updates."""

    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_public: Optional[bool] = None
    max_annotations_per_task: Optional[int] = Field(None, ge=1, le=10)
    auto_assign_tasks: Optional[bool] = None
    require_review: Optional[bool] = None


class ProjectResponse(ProjectBase):
    """Schema for project data in responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    is_active: bool
    is_public: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    total_tasks: int
    completed_tasks: int
    total_annotations: int
    max_annotations_per_task: int
    auto_assign_tasks: bool
    require_review: bool
    completion_rate: float

    # Creator information
    creator: Optional[UserPublic] = None


class ProjectSummary(BaseModel):
    """Schema for project summary information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    completion_rate: float
    total_tasks: int
    completed_tasks: int
    member_count: int
    created_at: datetime


class ProjectMemberBase(BaseModel):
    """Base project member schema."""

    role: str = Field(..., description="Member role in project")


class ProjectMemberCreate(ProjectMemberBase):
    """Schema for adding project member."""

    user_id: UUID = Field(..., description="User ID to add as member")


class ProjectMemberUpdate(BaseModel):
    """Schema for updating project member."""

    role: Optional[str] = Field(None, description="New role for member")
    is_active: Optional[bool] = Field(None, description="Member active status")


class ProjectMemberResponse(ProjectMemberBase):
    """Schema for project member data in responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    joined_at: datetime
    left_at: Optional[datetime] = None
    tasks_assigned: int
    tasks_completed: int
    annotations_created: int
    completion_rate: float

    # User information
    user: UserPublic


class ProjectInvitation(BaseModel):
    """Schema for project invitation."""

    email: str = Field(..., description="Email of user to invite")
    role: str = Field(..., description="Role to assign to invited user")
    message: Optional[str] = Field(
        None, max_length=500, description="Invitation message"
    )


class ProjectStats(BaseModel):
    """Schema for project statistics."""

    model_config = ConfigDict(from_attributes=True)

    total_projects: int
    active_projects: int
    completed_projects: int
    total_members: int
    total_tasks: int
    total_annotations: int
    average_completion_rate: float


class ProjectListResponse(BaseModel):
    """Schema for project list responses with pagination."""

    items: List[ProjectResponse]
    total: int
    page: int
    size: int
    pages: int


class ProjectMemberListResponse(BaseModel):
    """Schema for project member list responses."""

    items: List[ProjectMemberResponse]
    total: int
    page: int
    size: int
    pages: int


class ProjectFilter(BaseModel):
    """Schema for project filtering parameters."""

    status: Optional[str] = Field(None, description="Filter by project status")
    created_by: Optional[UUID] = Field(None, description="Filter by creator")
    is_public: Optional[bool] = Field(None, description="Filter by public status")
    name: Optional[str] = Field(None, description="Search by project name")
    start_date_from: Optional[datetime] = Field(
        None, description="Filter by start date from"
    )
    start_date_to: Optional[datetime] = Field(
        None, description="Filter by start date to"
    )


class ProjectPermissions(BaseModel):
    """Schema for project permission information."""

    can_read: bool = False
    can_write: bool = False
    can_delete: bool = False
    can_manage_members: bool = False
    can_manage_tasks: bool = False
    can_review: bool = False
    is_admin: bool = False
