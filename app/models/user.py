"""User model definitions."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from app.models.base import BaseUUIDModel
from app.models.enums import GlobalRole


class User(BaseUUIDModel):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    # Basic Information
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=True)

    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Global Role
    global_role = Column(Enum(GlobalRole), default=GlobalRole.USER, nullable=False)

    # Profile Information
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)

    # Activity Tracking
    last_login = Column(DateTime, nullable=True)
    last_active = Column(DateTime, nullable=True)

    # Email Verification
    email_verified_at = Column(DateTime, nullable=True)

    # Account Status
    is_suspended = Column(Boolean, default=False, nullable=False)
    suspended_at = Column(DateTime, nullable=True)
    suspended_reason = Column(Text, nullable=True)

    # Relationships
    created_projects = relationship(
        "Project", back_populates="creator", foreign_keys="Project.created_by"
    )

    project_memberships = relationship(
        "ProjectMember",
        back_populates="user",
        foreign_keys="ProjectMember.user_id",
        cascade="all, delete-orphan",
    )

    assigned_tasks = relationship(
        "Task", back_populates="assignee", foreign_keys="Task.assigned_to"
    )

    created_tasks = relationship(
        "Task", back_populates="creator", foreign_keys="Task.created_by"
    )

    annotations = relationship(
        "Annotation", back_populates="annotator", foreign_keys="Annotation.annotator_id"
    )

    reviews = relationship(
        "AnnotationReview",
        back_populates="reviewer",
        foreign_keys="AnnotationReview.reviewer_id",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', name='{self.full_name}')>"

    @property
    def is_admin(self) -> bool:
        """Check if user has global admin privileges."""
        return self.global_role == GlobalRole.ADMIN

    @property
    def is_system_admin(self) -> bool:
        """Check if user has system admin privileges."""
        return self.global_role == GlobalRole.SYSTEM_ADMIN

    def has_project_access(self, project_id: str) -> bool:
        """Check if user has access to a specific project."""
        return any(
            str(membership.project_id) == project_id
            for membership in self.project_memberships
            if membership.is_active
        )

    def get_project_role(self, project_id: str) -> Optional[str]:
        """Get user's role in a specific project."""
        for membership in self.project_memberships:
            if str(membership.project_id) == project_id and membership.is_active:
                return membership.role
        return None
