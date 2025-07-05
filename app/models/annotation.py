"""Annotation model definitions."""

from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from app.models.base import BaseProjectModel
from app.models.enums import AnnotationStatus, ReviewStatus


class Annotation(BaseProjectModel):
    """Annotation model for point cloud labeling."""

    __tablename__ = "annotations"

    # Task and User
    task_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True
    )

    annotator_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Vehicle Classification
    vehicle_type_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("project_vehicle_types.id"),
        nullable=True,
    )

    vehicle_type_name = Column(String(100), nullable=True)  # Cached for performance

    # Annotation Data
    confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    notes = Column(Text, nullable=True)

    # Status
    status = Column(
        Enum(AnnotationStatus),
        default=AnnotationStatus.DRAFT,
        nullable=False,
        index=True,
    )

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)

    # Quality Metrics
    time_spent = Column(Integer, nullable=True)  # seconds
    quality_score = Column(Integer, nullable=True)  # 1-10 scale

    # Additional Data
    extra_data = Column(JSON, nullable=True)  # Additional annotation data

    # Version Control
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    task = relationship("Task", back_populates="annotations")

    annotator = relationship(
        "User", back_populates="annotations", foreign_keys=[annotator_id]
    )

    vehicle_type = relationship("ProjectVehicleType", back_populates="annotations")

    reviews = relationship(
        "AnnotationReview", back_populates="annotation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Annotation(id={self.id}, task_id={self.task_id}, status='{self.status}')>"

    @property
    def is_submitted(self) -> bool:
        """Check if annotation has been submitted."""
        return self.status != AnnotationStatus.DRAFT

    @property
    def is_approved(self) -> bool:
        """Check if annotation has been approved."""
        return self.status == AnnotationStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        """Check if annotation has been rejected."""
        return self.status == AnnotationStatus.REJECTED

    @property
    def needs_review(self) -> bool:
        """Check if annotation needs review."""
        return self.status == AnnotationStatus.SUBMITTED

    @property
    def latest_review(self) -> Optional["AnnotationReview"]:
        """Get the latest review for this annotation."""
        if not self.reviews:
            return None
        return max(self.reviews, key=lambda r: r.created_at)

    def submit(self) -> None:
        """Submit annotation for review."""
        if self.status == AnnotationStatus.DRAFT:
            self.status = AnnotationStatus.SUBMITTED
            self.submitted_at = datetime.utcnow()

    def approve(self) -> None:
        """Approve annotation."""
        if self.status in [AnnotationStatus.SUBMITTED, AnnotationStatus.NEEDS_REVISION]:
            self.status = AnnotationStatus.APPROVED

    def reject(self) -> None:
        """Reject annotation."""
        if self.status in [AnnotationStatus.SUBMITTED, AnnotationStatus.NEEDS_REVISION]:
            self.status = AnnotationStatus.REJECTED

    def request_revision(self) -> None:
        """Request revision for annotation."""
        if self.status == AnnotationStatus.SUBMITTED:
            self.status = AnnotationStatus.NEEDS_REVISION

    def calculate_time_spent(self) -> int:
        """Calculate time spent on annotation in seconds."""
        if not self.submitted_at:
            return 0

        time_diff = self.submitted_at - self.started_at
        return int(time_diff.total_seconds())


class AnnotationReview(BaseProjectModel):
    """Annotation review model for quality control."""

    __tablename__ = "annotation_reviews"

    # Annotation and Reviewer
    annotation_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("annotations.id"),
        nullable=False,
        index=True,
    )

    reviewer_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Review Status
    status = Column(
        Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False, index=True
    )

    # Review Content
    comments = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)  # 1-5 scale

    # Specific Feedback
    feedback = Column(JSON, nullable=True)  # Structured feedback

    # Timing
    reviewed_at = Column(DateTime, nullable=True)

    # Relationships
    annotation = relationship("Annotation", back_populates="reviews")

    reviewer = relationship(
        "User", back_populates="reviews", foreign_keys=[reviewer_id]
    )

    def __repr__(self) -> str:
        return f"<AnnotationReview(id={self.id}, annotation_id={self.annotation_id}, status='{self.status}')>"

    @property
    def is_completed(self) -> bool:
        """Check if review has been completed."""
        return self.status != ReviewStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """Check if review approved the annotation."""
        return self.status == ReviewStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        """Check if review rejected the annotation."""
        return self.status == ReviewStatus.REJECTED

    def approve(
        self, comments: Optional[str] = None, rating: Optional[int] = None
    ) -> None:
        """Approve the annotation."""
        self.status = ReviewStatus.APPROVED
        self.comments = comments
        self.rating = rating
        self.reviewed_at = datetime.utcnow()

    def reject(
        self, comments: Optional[str] = None, rating: Optional[int] = None
    ) -> None:
        """Reject the annotation."""
        self.status = ReviewStatus.REJECTED
        self.comments = comments
        self.rating = rating
        self.reviewed_at = datetime.utcnow()

    def request_revision(
        self, comments: Optional[str] = None, rating: Optional[int] = None
    ) -> None:
        """Request revision for the annotation."""
        self.status = ReviewStatus.NEEDS_REVISION
        self.comments = comments
        self.rating = rating
        self.reviewed_at = datetime.utcnow()
