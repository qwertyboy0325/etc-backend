"""Models package initialization."""

from app.models.annotation import Annotation, AnnotationReview
from app.models.base import Base, BaseProjectModel, BaseUUIDModel
from app.models.enums import (
    AnnotationStatus,
    FileStatus,
    GlobalRole,
    NotificationStatus,
    NotificationType,
    ProjectRole,
    ProjectStatus,
    ReviewStatus,
    TaskPriority,
    TaskStatus,
    VehicleTypeSource,
)
from app.models.notification import Notification
from app.models.pointcloud import PointCloudFile
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.vehicle_type import GlobalVehicleType, ProjectVehicleType

__all__ = [
    # Base classes
    "Base",
    "BaseUUIDModel",
    "BaseProjectModel",
    # Enums
    "GlobalRole",
    "ProjectRole",
    "ProjectStatus",
    "TaskStatus",
    "TaskPriority",
    "AnnotationStatus",
    "ReviewStatus",
    "FileStatus",
    "VehicleTypeSource",
    "NotificationType",
    "NotificationStatus",
    # Models
    "User",
    "Project",
    "ProjectMember",
    "Task",
    "Annotation",
    "AnnotationReview",
    "GlobalVehicleType",
    "ProjectVehicleType",
    "PointCloudFile",
    "Notification",
]
