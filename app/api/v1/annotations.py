"""Annotation management API endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_db,
    require_project_access,
    validate_project_exists,
)
from app.models.enums import AnnotationStatus, ProjectRole, ReviewStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.annotation import (
    AnnotationCreate,
    AnnotationFilter,
    AnnotationListResponse,
    AnnotationResponse,
    AnnotationReviewCreate,
    AnnotationReviewResponse,
    AnnotationStats,
    AnnotationSubmit,
    AnnotationUpdate,
    BulkAnnotationReview,
    BulkAnnotationReviewResponse,
)
from app.services.annotation import AnnotationService

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_annotation_service(
    db: AsyncSession = Depends(get_db),
) -> AnnotationService:
    """Get annotation service instance."""
    return AnnotationService(db)


async def require_annotation_access(
    annotation_id: UUID,
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
) -> None:
    """Require access to a specific annotation."""
    annotation = await annotation_service.get_annotation(annotation_id, project_id)
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found"
        )

    # Users can access their own annotations or if they have reviewer role
    if annotation.annotator_id != current_user.id and not await require_project_access(
        project_id, [ProjectRole.PROJECT_ADMIN, ProjectRole.REVIEWER], current_user
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this annotation",
        )


# Annotation CRUD endpoints
@router.post(
    "/projects/{project_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new annotation",
    description="Create a new annotation for a task.",
)
async def create_annotation(
    project_id: UUID,
    annotation_data: AnnotationCreate,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: Project = Depends(validate_project_exists),
) -> AnnotationResponse:
    """Create a new annotation."""
    try:
        # Verify user has access to the project
        await require_project_access(
            project_id, [ProjectRole.PROJECT_ADMIN, ProjectRole.ANNOTATOR], current_user
        )

        annotation = await annotation_service.create_annotation(
            task_id=annotation_data.task_id,
            annotator_id=current_user.id,
            project_id=project_id,
            vehicle_type_id=annotation_data.vehicle_type_id,
            confidence=annotation_data.confidence,
            notes=annotation_data.notes,
            annotation_data=annotation_data.annotation_data,
        )

        logger.info(f"Created annotation {annotation.id} for user {current_user.id}")
        return AnnotationResponse.model_validate(annotation)

    except Exception as e:
        logger.error(f"Error creating annotation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/projects/{project_id}/annotations/{annotation_id}",
    response_model=AnnotationResponse,
    summary="Get annotation details",
    description="Get detailed information about a specific annotation.",
)
async def get_annotation(
    project_id: UUID,
    annotation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: None = Depends(require_annotation_access),
) -> AnnotationResponse:
    """Get annotation by ID."""
    annotation = await annotation_service.get_annotation(annotation_id, project_id)
    return AnnotationResponse.model_validate(annotation)


@router.put(
    "/projects/{project_id}/annotations/{annotation_id}",
    response_model=AnnotationResponse,
    summary="Update annotation",
    description="Update an existing annotation (only draft or needs revision status).",
)
async def update_annotation(
    project_id: UUID,
    annotation_id: UUID,
    annotation_data: AnnotationUpdate,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: None = Depends(require_annotation_access),
) -> AnnotationResponse:
    """Update an existing annotation."""
    try:
        annotation = await annotation_service.update_annotation(
            annotation_id=annotation_id,
            project_id=project_id,
            annotator_id=current_user.id,
            vehicle_type_id=annotation_data.vehicle_type_id,
            confidence=annotation_data.confidence,
            notes=annotation_data.notes,
            annotation_data=annotation_data.annotation_data,
        )

        logger.info(f"Updated annotation {annotation_id} by user {current_user.id}")
        return AnnotationResponse.model_validate(annotation)

    except Exception as e:
        logger.error(f"Error updating annotation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/projects/{project_id}/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete annotation",
    description="Delete an annotation (only draft status).",
)
async def delete_annotation(
    project_id: UUID,
    annotation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: None = Depends(require_annotation_access),
) -> None:
    """Delete an annotation."""
    try:
        await annotation_service.delete_annotation(
            annotation_id=annotation_id, project_id=project_id, user_id=current_user.id
        )

        logger.info(f"Deleted annotation {annotation_id} by user {current_user.id}")

    except Exception as e:
        logger.error(f"Error deleting annotation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Annotation workflow endpoints
@router.post(
    "/projects/{project_id}/annotations/{annotation_id}/submit",
    response_model=AnnotationResponse,
    summary="Submit annotation for review",
    description="Submit an annotation for review process.",
)
async def submit_annotation(
    project_id: UUID,
    annotation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: None = Depends(require_annotation_access),
) -> AnnotationResponse:
    """Submit annotation for review."""
    try:
        annotation = await annotation_service.submit_annotation(
            annotation_id=annotation_id,
            project_id=project_id,
            annotator_id=current_user.id,
        )

        logger.info(
            f"Submitted annotation {annotation_id} for review by user {current_user.id}"
        )
        return AnnotationResponse.model_validate(annotation)

    except Exception as e:
        logger.error(f"Error submitting annotation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Review endpoints
@router.post(
    "/projects/{project_id}/annotations/{annotation_id}/review",
    response_model=AnnotationReviewResponse,
    summary="Review annotation",
    description="Review an annotation (approve, reject, or request revision).",
)
async def review_annotation(
    project_id: UUID,
    annotation_id: UUID,
    review_data: AnnotationReviewCreate,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: Project = Depends(validate_project_exists),
) -> AnnotationReviewResponse:
    """Review an annotation."""
    try:
        # Verify user has reviewer permissions
        await require_project_access(
            project_id, [ProjectRole.PROJECT_ADMIN, ProjectRole.REVIEWER], current_user
        )

        review = await annotation_service.review_annotation(
            annotation_id=annotation_id,
            project_id=project_id,
            reviewer_id=current_user.id,
            status=review_data.status,
            comments=review_data.comments,
            rating=review_data.rating,
        )

        logger.info(
            f"Reviewed annotation {annotation_id} with status {review_data.status} by user {current_user.id}"
        )
        return AnnotationReviewResponse.model_validate(review)

    except Exception as e:
        logger.error(f"Error reviewing annotation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/projects/{project_id}/reviews/pending",
    response_model=List[AnnotationResponse],
    summary="Get pending reviews",
    description="Get list of annotations pending review.",
)
async def get_pending_reviews(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: Project = Depends(validate_project_exists),
) -> List[AnnotationResponse]:
    """Get annotations pending review."""
    try:
        # Verify user has reviewer permissions
        await require_project_access(
            project_id, [ProjectRole.PROJECT_ADMIN, ProjectRole.REVIEWER], current_user
        )

        annotations = await annotation_service.get_pending_reviews(project_id)
        return [
            AnnotationResponse.model_validate(annotation) for annotation in annotations
        ]

    except Exception as e:
        logger.error(f"Error getting pending reviews: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/projects/{project_id}/reviews/bulk",
    response_model=BulkAnnotationReviewResponse,
    summary="Bulk review annotations",
    description="Review multiple annotations at once.",
)
async def bulk_review_annotations(
    project_id: UUID,
    review_data: BulkAnnotationReview,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: Project = Depends(validate_project_exists),
) -> BulkAnnotationReviewResponse:
    """Bulk review multiple annotations."""
    try:
        # Verify user has reviewer permissions
        await require_project_access(
            project_id, [ProjectRole.PROJECT_ADMIN, ProjectRole.REVIEWER], current_user
        )

        success_count = 0
        failed_count = 0
        failed_ids = []
        errors = []

        for annotation_id in review_data.annotation_ids:
            try:
                await annotation_service.review_annotation(
                    annotation_id=annotation_id,
                    project_id=project_id,
                    reviewer_id=current_user.id,
                    status=review_data.status,
                    comments=review_data.comments,
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                failed_ids.append(annotation_id)
                errors.append(f"Annotation {annotation_id}: {str(e)}")

        logger.info(
            f"Bulk reviewed {success_count} annotations, {failed_count} failed by user {current_user.id}"
        )

        return BulkAnnotationReviewResponse(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            errors=errors,
        )

    except Exception as e:
        logger.error(f"Error in bulk review: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Query and list endpoints
@router.get(
    "/projects/{project_id}/annotations",
    response_model=AnnotationListResponse,
    summary="List annotations",
    description="Get list of annotations with filtering and pagination.",
)
async def list_annotations(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: Project = Depends(validate_project_exists),
    # Query parameters
    status: Optional[AnnotationStatus] = Query(
        None, description="Filter by annotation status"
    ),
    annotator_id: Optional[UUID] = Query(None, description="Filter by annotator"),
    task_id: Optional[UUID] = Query(None, description="Filter by task"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> AnnotationListResponse:
    """List annotations with filtering and pagination."""
    try:
        # Verify user has access to project
        await require_project_access(
            project_id,
            [
                ProjectRole.PROJECT_ADMIN,
                ProjectRole.ANNOTATOR,
                ProjectRole.REVIEWER,
                ProjectRole.VIEWER,
            ],
            current_user,
        )

        # For annotators, only show their own annotations unless they have reviewer+ permissions
        if not await require_project_access(
            project_id,
            [ProjectRole.PROJECT_ADMIN, ProjectRole.REVIEWER],
            current_user,
            raise_error=False,
        ):
            annotator_id = current_user.id

        annotations = await annotation_service.get_user_annotations(
            annotator_id=annotator_id or current_user.id,
            project_id=project_id,
            status=status,
            limit=size,
            offset=(page - 1) * size,
        )

        # For pagination, we need total count
        total_annotations = await annotation_service.get_user_annotations(
            annotator_id=annotator_id or current_user.id,
            project_id=project_id,
            status=status,
        )
        total = len(total_annotations)
        pages = (total + size - 1) // size

        return AnnotationListResponse(
            items=[
                AnnotationResponse.model_validate(annotation)
                for annotation in annotations
            ],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    except Exception as e:
        logger.error(f"Error listing annotations: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/projects/{project_id}/tasks/{task_id}/annotations",
    response_model=List[AnnotationResponse],
    summary="Get task annotations",
    description="Get all annotations for a specific task.",
)
async def get_task_annotations(
    project_id: UUID,
    task_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: Project = Depends(validate_project_exists),
) -> List[AnnotationResponse]:
    """Get all annotations for a specific task."""
    try:
        # Verify user has access to project
        await require_project_access(
            project_id,
            [
                ProjectRole.PROJECT_ADMIN,
                ProjectRole.ANNOTATOR,
                ProjectRole.REVIEWER,
                ProjectRole.VIEWER,
            ],
            current_user,
        )

        annotations = await annotation_service.get_task_annotations(task_id, project_id)
        return [
            AnnotationResponse.model_validate(annotation) for annotation in annotations
        ]

    except Exception as e:
        logger.error(f"Error getting task annotations: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Statistics endpoints
@router.get(
    "/projects/{project_id}/annotations/stats",
    response_model=AnnotationStats,
    summary="Get annotation statistics",
    description="Get annotation statistics for the project or specific annotator.",
)
async def get_annotation_statistics(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    _: Project = Depends(validate_project_exists),
    annotator_id: Optional[UUID] = Query(
        None, description="Get stats for specific annotator"
    ),
) -> AnnotationStats:
    """Get annotation statistics."""
    try:
        # Verify user has access to project
        await require_project_access(
            project_id,
            [
                ProjectRole.PROJECT_ADMIN,
                ProjectRole.ANNOTATOR,
                ProjectRole.REVIEWER,
                ProjectRole.VIEWER,
            ],
            current_user,
        )

        # For annotators, only show their own stats unless they have reviewer+ permissions
        if not await require_project_access(
            project_id,
            [ProjectRole.PROJECT_ADMIN, ProjectRole.REVIEWER],
            current_user,
            raise_error=False,
        ):
            annotator_id = current_user.id

        stats = await annotation_service.get_annotation_statistics(
            project_id=project_id, annotator_id=annotator_id
        )

        return AnnotationStats(**stats)

    except Exception as e:
        logger.error(f"Error getting annotation statistics: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
