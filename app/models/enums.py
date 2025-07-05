"""Enum definitions for models."""

from enum import Enum


class GlobalRole(str, Enum):
    """Global user roles."""

    SYSTEM_ADMIN = "system_admin"  # 系統管理員
    ADMIN = "admin"  # 管理員
    USER = "user"  # 一般使用者


class ProjectRole(str, Enum):
    """Project-specific user roles."""

    PROJECT_ADMIN = "project_admin"  # 專案管理員
    ANNOTATOR = "annotator"  # 標注員
    REVIEWER = "reviewer"  # 審核員
    VIEWER = "viewer"  # 查看者


class ProjectStatus(str, Enum):
    """Project status."""

    ACTIVE = "active"  # 進行中
    PAUSED = "paused"  # 暫停
    COMPLETED = "completed"  # 已完成
    ARCHIVED = "archived"  # 已歸檔


class TaskStatus(str, Enum):
    """Task status."""

    PENDING = "pending"  # 待分配
    ASSIGNED = "assigned"  # 已分配
    IN_PROGRESS = "in_progress"  # 進行中
    COMPLETED = "completed"  # 已完成
    REVIEWED = "reviewed"  # 已審核
    REJECTED = "rejected"  # 被拒絕
    CANCELLED = "cancelled"  # 已取消


class TaskPriority(str, Enum):
    """Task priority."""

    LOW = "low"  # 低優先級
    MEDIUM = "medium"  # 中優先級
    HIGH = "high"  # 高優先級
    URGENT = "urgent"  # 緊急


class AnnotationStatus(str, Enum):
    """Annotation status."""

    DRAFT = "draft"  # 草稿
    SUBMITTED = "submitted"  # 已提交
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 被拒絕
    NEEDS_REVISION = "needs_revision"  # 需要修改


class ReviewStatus(str, Enum):
    """Review status."""

    PENDING = "pending"  # 待審核
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 被拒絕
    NEEDS_REVISION = "needs_revision"  # 需要修改


class FileStatus(str, Enum):
    """File processing status."""

    UPLOADING = "uploading"  # 上傳中
    UPLOADED = "uploaded"  # 已上傳
    PROCESSING = "processing"  # 處理中
    PROCESSED = "processed"  # 已處理
    FAILED = "failed"  # 處理失敗
    DELETED = "deleted"  # 已刪除


class VehicleTypeSource(str, Enum):
    """Vehicle type source."""

    GLOBAL = "global"  # 全局車種
    PROJECT = "project"  # 專案車種


class NotificationType(str, Enum):
    """Notification type."""

    INFO = "info"  # 信息
    WARNING = "warning"  # 警告
    ERROR = "error"  # 錯誤
    SUCCESS = "success"  # 成功
    TASK_ASSIGNED = "task_assigned"  # 任務分配
    TASK_COMPLETED = "task_completed"  # 任務完成
    REVIEW_REQUESTED = "review_requested"  # 審核請求
    REVIEW_COMPLETED = "review_completed"  # 審核完成
    PROJECT_INVITATION = "project_invitation"  # 專案邀請


class NotificationStatus(str, Enum):
    """Notification status."""

    UNREAD = "unread"  # 未讀
    READ = "read"  # 已讀
    ARCHIVED = "archived"  # 已歸檔
