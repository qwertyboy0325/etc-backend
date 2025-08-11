"""Annotation management service for point cloud annotation workflow."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.annotation import Annotation, AnnotationReview
from app.models.enums import AnnotationStatus, ProjectRole, ReviewStatus
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.vehicle_type import ProjectVehicleType

logger = logging.getLogger(__name__)


class AnnotationService:
    """Service for managing point cloud annotations."""

    def __init__(self, db: AsyncSession):
        """Initialize annotation service with database session."""
        self.db = db

    async def create_annotation(
        self,
        task_id: UUID,
        annotator_id: UUID,
        project_id: UUID,
        vehicle_type_id: Optional[UUID] = None,
        confidence: Optional[float] = None,
        notes: Optional[str] = None,
        annotation_data: Optional[Dict[str, Any]] = None,
    ) -> Annotation:
        """Create a new annotation for a task."""
        try:
            # Verify task exists and belongs to project
            task = await self.db.get(Task, task_id)
            if not task or task.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found in this project",
                )

            # Verify task is assigned to annotator
            if task.assigned_to != annotator_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Task is not assigned to this user",
                )

            # Verify vehicle type belongs to project if provided
            if vehicle_type_id:
                vehicle_type = await self.db.get(ProjectVehicleType, vehicle_type_id)
                if not vehicle_type or vehicle_type.project_id != project_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Vehicle type not found in this project",
                    )

            # Create annotation
            annotation = Annotation(
                project_id=project_id,
                task_id=task_id,
                annotator_id=annotator_id,
                vehicle_type_id=vehicle_type_id,
                confidence=confidence,
                notes=notes,
                extra_data=annotation_data or {},
                status=AnnotationStatus.DRAFT,
            )

            self.db.add(annotation)
            await self.db.commit()
            await self.db.refresh(annotation)

            logger.info(f"Created annotation {annotation.id} for task {task_id}")
            return annotation

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating annotation: {str(e)}")
            raise

    async def get_annotation(
        self, annotation_id: UUID, project_id: UUID
    ) -> Optional[Annotation]:
        """Get annotation by ID within project context."""
        query = (
            select(Annotation)
            .where(
                and_(
                    Annotation.id == annotation_id, Annotation.project_id == project_id
                )
            )
            .options(
                selectinload(Annotation.task),
                selectinload(Annotation.annotator),
                selectinload(Annotation.vehicle_type),
                selectinload(Annotation.reviews),
            )
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_task_annotations(
        self, task_id: UUID, project_id: UUID
    ) -> List[Annotation]:
        """Get all annotations for a specific task."""
        query = (
            select(Annotation)
            .where(
                and_(Annotation.task_id == task_id, Annotation.project_id == project_id)
            )
            .options(
                selectinload(Annotation.annotator),
                selectinload(Annotation.vehicle_type),
                selectinload(Annotation.reviews),
            )
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_user_annotations(
        self,
        annotator_id: UUID,
        project_id: UUID,
        status: Optional[AnnotationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Annotation]:
        """Get annotations by user with optional status filter."""
        conditions = [
            Annotation.annotator_id == annotator_id,
            Annotation.project_id == project_id,
        ]

        if status:
            conditions.append(Annotation.status == status)

        query = (
            select(Annotation)
            .where(and_(*conditions))
            .options(
                selectinload(Annotation.task), selectinload(Annotation.vehicle_type)
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_annotation(
        self,
        annotation_id: UUID,
        project_id: UUID,
        annotator_id: UUID,
        vehicle_type_id: Optional[UUID] = None,
        confidence: Optional[float] = None,
        notes: Optional[str] = None,
        annotation_data: Optional[Dict[str, Any]] = None,
    ) -> Annotation:
        """Update an existing annotation."""
        try:
            annotation = await self.get_annotation(annotation_id, project_id)
            if not annotation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found"
                )

            # Verify user can edit this annotation
            if annotation.annotator_id != annotator_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot edit annotation created by another user",
                )

            # Can only edit draft or revision-requested annotations
            if annotation.status not in [
                AnnotationStatus.DRAFT,
                AnnotationStatus.NEEDS_REVISION,
            ]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot edit submitted or approved annotations",
                )

            # Update fields
            if vehicle_type_id is not None:
                # Verify vehicle type belongs to project
                vehicle_type = await self.db.get(ProjectVehicleType, vehicle_type_id)
                if not vehicle_type or vehicle_type.project_id != project_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Vehicle type not found in this project",
                    )
                annotation.vehicle_type_id = vehicle_type_id

            if confidence is not None:
                annotation.confidence = confidence

            if notes is not None:
                annotation.notes = notes

            if annotation_data is not None:
                annotation.extra_data = annotation_data

            await self.db.commit()
            await self.db.refresh(annotation)

            logger.info(f"Updated annotation {annotation_id}")
            return annotation

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating annotation: {str(e)}")
            raise

    async def submit_annotation(
        self, annotation_id: UUID, project_id: UUID, annotator_id: UUID
    ) -> Annotation:
        """Submit annotation for review."""
        try:
            annotation = await self.get_annotation(annotation_id, project_id)
            if not annotation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found"
                )

            # Verify user can submit this annotation
            if annotation.annotator_id != annotator_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot submit annotation created by another user",
                )

            # Can only submit draft or revision-requested annotations
            if annotation.status not in [
                AnnotationStatus.DRAFT,
                AnnotationStatus.NEEDS_REVISION,
            ]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Annotation is already submitted or approved",
                )

            # Validate annotation completeness
            if not annotation.vehicle_type_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vehicle type is required before submission",
                )

            # Submit annotation
            annotation.status = AnnotationStatus.SUBMITTED
            annotation.submitted_at = datetime.utcnow()

            # Calculate time spent
            if annotation.started_at:
                time_diff = annotation.submitted_at - annotation.started_at
                annotation.time_spent = int(time_diff.total_seconds())

            await self.db.commit()
            await self.db.refresh(annotation)

            logger.info(f"Submitted annotation {annotation_id} for review")
            return annotation

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error submitting annotation: {str(e)}")
            raise

    async def review_annotation(
        self,
        annotation_id: UUID,
        project_id: UUID,
        reviewer_id: UUID,
        status: ReviewStatus,
        comments: Optional[str] = None,
        rating: Optional[int] = None,
    ) -> AnnotationReview:
        """Review an annotation (approve, reject, or request revision)."""
        try:
            # Verify annotation exists and is submitted
            annotation = await self.get_annotation(annotation_id, project_id)
            if not annotation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found"
                )

            if annotation.status != AnnotationStatus.SUBMITTED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Annotation is not in submitted status",
                )

            # Verify reviewer has permission
            await self._verify_reviewer_permission(reviewer_id, project_id)

            # Create review record
            review = AnnotationReview(
                project_id=project_id,
                annotation_id=annotation_id,
                reviewer_id=reviewer_id,
                status=status,
                comments=comments,
                rating=rating,
                reviewed_at=datetime.utcnow(),
            )

            # Update annotation status based on review
            if status == ReviewStatus.APPROVED:
                annotation.status = AnnotationStatus.APPROVED
            elif status == ReviewStatus.REJECTED:
                annotation.status = AnnotationStatus.REJECTED
            elif status == ReviewStatus.NEEDS_REVISION:
                annotation.status = AnnotationStatus.NEEDS_REVISION

            self.db.add(review)
            await self.db.commit()
            await self.db.refresh(review)

            logger.info(f"Reviewed annotation {annotation_id} with status {status}")
            return review

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error reviewing annotation: {str(e)}")
            raise

    async def get_pending_reviews(
        self, project_id: UUID, reviewer_id: Optional[UUID] = None
    ) -> List[Annotation]:
        """Get annotations pending review."""
        conditions = [
            Annotation.project_id == project_id,
            Annotation.status == AnnotationStatus.SUBMITTED,
        ]

        query = (
            select(Annotation)
            .where(and_(*conditions))
            .options(
                selectinload(Annotation.task),
                selectinload(Annotation.annotator),
                selectinload(Annotation.vehicle_type),
            )
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_annotation_statistics(
        self, project_id: UUID, annotator_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get annotation statistics for project or specific annotator."""
        conditions = [Annotation.project_id == project_id]
        if annotator_id:
            conditions.append(Annotation.annotator_id == annotator_id)

        # Count by status
        query = (
            select(Annotation.status, func.count(Annotation.id).label("count"))
            .where(and_(*conditions))
            .group_by(Annotation.status)
        )

        result = await self.db.execute(query)
        status_counts = {row.status: row.count for row in result}

        # Average confidence
        confidence_query = select(
            func.avg(Annotation.confidence).label("avg_confidence")
        ).where(and_(*conditions + [Annotation.confidence.isnot(None)]))

        confidence_result = await self.db.execute(confidence_query)
        avg_confidence = confidence_result.scalar() or 0.0

        return {
            "status_counts": status_counts,
            "average_confidence": float(avg_confidence),
            "total_annotations": sum(status_counts.values()),
        }

    async def _verify_reviewer_permission(
        self, user_id: UUID, project_id: UUID
    ) -> None:
        """Verify user has reviewer permissions in project."""
        query = select(ProjectMember).where(
            and_(
                ProjectMember.user_id == user_id,
                ProjectMember.project_id == project_id,
                ProjectMember.is_active == True,
            )
        )

        result = await self.db.execute(query)
        member = result.scalar_one_or_none()

        if not member or member.role not in [
            ProjectRole.PROJECT_ADMIN,
            ProjectRole.REVIEWER,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to review annotations",
            )

    async def delete_annotation(
        self, annotation_id: UUID, project_id: UUID, user_id: UUID
    ) -> bool:
        """Delete an annotation (only if draft status)."""
        try:
            annotation = await self.get_annotation(annotation_id, project_id)
            if not annotation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found"
                )

            # Verify user can delete this annotation
            if annotation.annotator_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete annotation created by another user",
                )

            # Can only delete draft annotations
            if annotation.status != AnnotationStatus.DRAFT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only delete draft annotations",
                )

            await self.db.delete(annotation)
            await self.db.commit()

            logger.info(f"Deleted annotation {annotation_id}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting annotation: {str(e)}")
            raise
