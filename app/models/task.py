"""Task model definitions."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
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
from app.models.enums import TaskPriority, TaskStatus


class Task(BaseProjectModel):
    """Task model for annotation workflow."""

    __tablename__ = "tasks"

    # Basic Information
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Status and Priority
    status = Column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )

    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)

    # Assignment
    assigned_to = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    assigned_at = Column(DateTime, nullable=True)

    created_by = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Point Cloud File
    pointcloud_file_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("pointcloud_files.id"), nullable=False
    )

    # Task Settings
    max_annotations = Column(Integer, default=3, nullable=False)
    require_review = Column(Boolean, default=True, nullable=False)

    # Deadlines
    due_date = Column(DateTime, nullable=True)

    # Completion
    completed_at = Column(DateTime, nullable=True)

    # Quality Control
    quality_score = Column(Integer, nullable=True)  # 1-10 scale

    # Instructions
    instructions = Column(Text, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="tasks")

    assignee = relationship(
        "User", back_populates="assigned_tasks", foreign_keys=[assigned_to]
    )

    creator = relationship(
        "User", back_populates="created_tasks", foreign_keys=[created_by]
    )

    pointcloud_file = relationship("PointCloudFile", back_populates="tasks")

    annotations = relationship(
        "Annotation", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, name='{self.name}', status='{self.status}')>"

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date and self.status not in [
            TaskStatus.COMPLETED,
            TaskStatus.REVIEWED,
            TaskStatus.CANCELLED,
        ]

    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.REVIEWED]

    @property
    def annotation_count(self) -> int:
        """Get number of annotations for this task."""
        return len([a for a in self.annotations if a.status != "draft"])

    @property
    def approved_annotation_count(self) -> int:
        """Get number of approved annotations."""
        return len([a for a in self.annotations if a.status == "approved"])

    @property
    def completion_rate(self) -> float:
        """Calculate task completion rate based on annotations."""
        if self.max_annotations == 0:
            return 0.0
        return (self.approved_annotation_count / self.max_annotations) * 100

    def can_be_assigned_to(self, user_id: str) -> bool:
        """Check if task can be assigned to specific user."""
        if self.status != TaskStatus.PENDING:
            return False

        # Check if user is a member of the project
        from app.models.enums import ProjectRole
        from app.models.project import ProjectMember

        # Note: This would require a database query in real implementation
        # For now, we'll assume validation is done at the service level
        return True

    def assign_to_user(self, user_id: str) -> None:
        """Assign task to a user."""
        if self.can_be_assigned_to(user_id):
            self.assigned_to = user_id
            self.assigned_at = datetime.utcnow()
            self.status = TaskStatus.ASSIGNED

    def mark_in_progress(self) -> None:
        """Mark task as in progress."""
        if self.status == TaskStatus.ASSIGNED:
            self.status = TaskStatus.IN_PROGRESS

    def mark_completed(self) -> None:
        """Mark task as completed."""
        if self.status == TaskStatus.IN_PROGRESS:
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.utcnow()

    def get_time_spent(self) -> Optional[float]:
        """Calculate time spent on task in hours."""
        if not self.assigned_at:
            return None

        end_time = self.completed_at or datetime.utcnow()
        time_diff = end_time - self.assigned_at
        return time_diff.total_seconds() / 3600  # Convert to hours
