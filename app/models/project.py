"""Project model definitions."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from app.models.base import BaseUUIDModel
from app.models.enums import ProjectRole, ProjectStatus


class Project(BaseUUIDModel):
    """Project model for multi-project architecture."""

    __tablename__ = "projects"

    # Basic Information
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Status
    status = Column(
        Enum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False, index=True
    )

    # Owner and Creation
    created_by = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Project Settings
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)

    # Statistics
    total_tasks = Column(Integer, default=0, nullable=False)
    completed_tasks = Column(Integer, default=0, nullable=False)
    total_annotations = Column(Integer, default=0, nullable=False)

    # Dates
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    # Configuration
    max_annotations_per_task = Column(Integer, default=3, nullable=False)
    auto_assign_tasks = Column(Boolean, default=True, nullable=False)
    require_review = Column(Boolean, default=True, nullable=False)

    # Relationships
    creator = relationship(
        "User", back_populates="created_projects", foreign_keys=[created_by]
    )

    members = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    vehicle_types = relationship(
        "ProjectVehicleType", back_populates="project", cascade="all, delete-orphan"
    )

    pointcloud_files = relationship(
        "PointCloudFile", back_populates="project", cascade="all, delete-orphan"
    )

    notifications = relationship(
        "Notification", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"

    @property
    def completion_rate(self) -> float:
        """Calculate project completion rate."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def is_completed(self) -> bool:
        """Check if project is completed."""
        return self.status == ProjectStatus.COMPLETED

    def get_member_count(self) -> int:
        """Get total number of active members."""
        return len([m for m in self.members if m.is_active])

    def get_members_by_role(self, role: ProjectRole) -> List["ProjectMember"]:
        """Get members by specific role."""
        return [m for m in self.members if m.role == role and m.is_active]


class ProjectMember(BaseUUIDModel):
    """Project membership model."""

    __tablename__ = "project_members"

    # Core Fields
    project_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Role and Status
    role = Column(Enum(ProjectRole), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    # Membership Dates
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)

    # Invitation
    invited_by = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    invitation_accepted_at = Column(DateTime, nullable=True)

    # Performance Stats
    tasks_assigned = Column(Integer, default=0, nullable=False)
    tasks_completed = Column(Integer, default=0, nullable=False)
    annotations_created = Column(Integer, default=0, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="members")

    user = relationship(
        "User", back_populates="project_memberships", foreign_keys=[user_id]
    )

    inviter = relationship("User", foreign_keys=[invited_by])

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    def __repr__(self) -> str:
        return f"<ProjectMember(project_id={self.project_id}, user_id={self.user_id}, role='{self.role}')>"

    @property
    def completion_rate(self) -> float:
        """Calculate member's task completion rate."""
        if self.tasks_assigned == 0:
            return 0.0
        return (self.tasks_completed / self.tasks_assigned) * 100

    def can_access_project(self) -> bool:
        """Check if member can access the project."""
        return self.is_active and self.project.is_active

    def has_permission(self, permission: str) -> bool:
        """Check if member has specific permission."""
        role_permissions = {
            ProjectRole.PROJECT_ADMIN: [
                "project.manage",
                "project.view",
                "members.manage",
                "tasks.manage",
                "tasks.assign",
                "tasks.view",
                "annotations.view",
                "annotations.manage",
                "reviews.manage",
                "statistics.view",
            ],
            ProjectRole.ANNOTATOR: [
                "project.view",
                "tasks.view",
                "tasks.annotate",
                "annotations.create",
                "annotations.edit_own",
            ],
            ProjectRole.REVIEWER: [
                "project.view",
                "tasks.view",
                "annotations.view",
                "annotations.review",
                "reviews.create",
                "statistics.view",
            ],
            ProjectRole.VIEWER: [
                "project.view",
                "tasks.view",
                "annotations.view",
                "statistics.view",
            ],
        }

        return permission in role_permissions.get(self.role, [])
