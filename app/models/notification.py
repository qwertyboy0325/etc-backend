"""Notification model definitions."""

from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from app.models.base import BaseUUIDModel
from app.models.enums import NotificationStatus, NotificationType


class Notification(BaseUUIDModel):
    """Notification model for system and project notifications."""

    __tablename__ = "notifications"

    # Recipient
    user_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Project Context (optional)
    project_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )

    # Notification Type
    type = Column(Enum(NotificationType), nullable=False, index=True)

    # Content
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # Status
    status = Column(
        Enum(NotificationStatus),
        default=NotificationStatus.UNREAD,
        nullable=False,
        index=True,
    )

    # Timing
    read_at = Column(DateTime, nullable=True)

    # Related Entities
    related_task_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True
    )

    related_annotation_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("annotations.id"), nullable=True
    )

    # Additional Data
    extra_data = Column(JSON, nullable=True)  # Additional notification data

    # Action URL
    action_url = Column(String(500), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    project = relationship(
        "Project", back_populates="notifications", foreign_keys=[project_id]
    )

    related_task = relationship("Task", foreign_keys=[related_task_id])

    related_annotation = relationship(
        "Annotation", foreign_keys=[related_annotation_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, type='{self.type}', status='{self.status}')>"
        )

    @property
    def is_read(self) -> bool:
        """Check if notification has been read."""
        return self.status == NotificationStatus.READ

    @property
    def is_unread(self) -> bool:
        """Check if notification is unread."""
        return self.status == NotificationStatus.UNREAD

    @property
    def is_archived(self) -> bool:
        """Check if notification is archived."""
        return self.status == NotificationStatus.ARCHIVED

    @property
    def is_project_notification(self) -> bool:
        """Check if this is a project-specific notification."""
        return self.project_id is not None

    @property
    def is_system_notification(self) -> bool:
        """Check if this is a system notification."""
        return self.project_id is None

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        if self.status == NotificationStatus.UNREAD:
            self.status = NotificationStatus.READ
            self.read_at = datetime.utcnow()

    def mark_as_unread(self) -> None:
        """Mark notification as unread."""
        if self.status == NotificationStatus.READ:
            self.status = NotificationStatus.UNREAD
            self.read_at = None

    def archive(self) -> None:
        """Archive notification."""
        self.status = NotificationStatus.ARCHIVED
        if not self.read_at:
            self.read_at = datetime.utcnow()

    def unarchive(self) -> None:
        """Unarchive notification."""
        if self.status == NotificationStatus.ARCHIVED:
            self.status = (
                NotificationStatus.READ if self.read_at else NotificationStatus.UNREAD
            )

    @classmethod
    def create_task_assigned(
        cls,
        user_id: str,
        task_id: str,
        project_id: str,
        task_name: str,
        assigner_name: str,
    ) -> "Notification":
        """Create task assignment notification."""
        return cls(
            user_id=user_id,
            project_id=project_id,
            type=NotificationType.TASK_ASSIGNED,
            title="新任務分配",
            message=f"您被分配了一個新任務：{task_name}",
            related_task_id=task_id,
            extra_data={"task_name": task_name, "assigner_name": assigner_name},
            action_url=f"/projects/{project_id}/tasks/{task_id}",
        )

    @classmethod
    def create_task_completed(
        cls,
        user_id: str,
        task_id: str,
        project_id: str,
        task_name: str,
        annotator_name: str,
    ) -> "Notification":
        """Create task completion notification."""
        return cls(
            user_id=user_id,
            project_id=project_id,
            type=NotificationType.TASK_COMPLETED,
            title="任務已完成",
            message=f"任務 {task_name} 已由 {annotator_name} 完成",
            related_task_id=task_id,
            extra_data={"task_name": task_name, "annotator_name": annotator_name},
            action_url=f"/projects/{project_id}/tasks/{task_id}",
        )

    @classmethod
    def create_review_requested(
        cls,
        user_id: str,
        annotation_id: str,
        project_id: str,
        task_name: str,
        annotator_name: str,
    ) -> "Notification":
        """Create review request notification."""
        return cls(
            user_id=user_id,
            project_id=project_id,
            type=NotificationType.REVIEW_REQUESTED,
            title="審核請求",
            message=f"{annotator_name} 已完成 {task_name} 的標注，請進行審核",
            related_annotation_id=annotation_id,
            extra_data={"task_name": task_name, "annotator_name": annotator_name},
            action_url=f"/projects/{project_id}/annotations/{annotation_id}/review",
        )

    @classmethod
    def create_review_completed(
        cls,
        user_id: str,
        annotation_id: str,
        project_id: str,
        task_name: str,
        reviewer_name: str,
        approved: bool,
    ) -> "Notification":
        """Create review completion notification."""
        status_text = "已批准" if approved else "需要修改"
        return cls(
            user_id=user_id,
            project_id=project_id,
            type=NotificationType.REVIEW_COMPLETED,
            title="審核完成",
            message=f"您的 {task_name} 標注已由 {reviewer_name} 審核，狀態：{status_text}",
            related_annotation_id=annotation_id,
            extra_data={
                "task_name": task_name,
                "reviewer_name": reviewer_name,
                "approved": approved,
            },
            action_url=f"/projects/{project_id}/annotations/{annotation_id}",
        )

    @classmethod
    def create_project_invitation(
        cls,
        user_id: str,
        project_id: str,
        project_name: str,
        inviter_name: str,
        role: str,
    ) -> "Notification":
        """Create project invitation notification."""
        return cls(
            user_id=user_id,
            project_id=project_id,
            type=NotificationType.PROJECT_INVITATION,
            title="專案邀請",
            message=f"{inviter_name} 邀請您加入專案 {project_name}，角色：{role}",
            extra_data={
                "project_name": project_name,
                "inviter_name": inviter_name,
                "role": role,
            },
            action_url=f"/projects/{project_id}/invitation",
        )

    @classmethod
    def create_system_notification(
        cls,
        user_id: str,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
    ) -> "Notification":
        """Create system notification."""
        return cls(
            user_id=user_id, type=notification_type, title=title, message=message
        )
