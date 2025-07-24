"""Project management API routes."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    require_project_admin,
    validate_project_exists,
)
from app.core.database import get_db
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectFilter,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberListResponse,
    ProjectMemberUpdate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_project_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    """Get project service instance."""
    return ProjectService(db)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """
    Create a new project.

    The current user will automatically become the project admin.

    - **name**: Project name (2-200 characters)
    - **description**: Optional project description
    - **start_date**: Optional project start date
    - **end_date**: Optional project end date
    - **is_public**: Whether the project is public (default: false)
    - **max_annotations_per_task**: Maximum annotations per task (1-10, default: 3)
    - **auto_assign_tasks**: Enable automatic task assignment (default: true)
    - **require_review**: Require review for annotations (default: true)
    """
    try:
        project = await project_service.create_project(project_data, current_user.id)

        # Convert to response format
        project_response = ProjectResponse.model_validate(project)
        project_response.completion_rate = project.completion_rate

        logger.info(
            f"Project created successfully: {project.name} by {current_user.email}"
        )
        return project_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project creation failed",
        )


@router.get("/", response_model=ProjectListResponse)
async def get_user_projects(
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by project status"
    ),
    name_filter: Optional[str] = Query(
        None, alias="name", description="Search by project name"
    ),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
) -> ProjectListResponse:
    """
    Get current user's projects with filtering and pagination.

    Returns projects where the user is a member.

    Query parameters:
    - **page**: Page number (starting from 1)
    - **size**: Items per page (1-100)
    - **status**: Filter by project status (active, paused, completed, archived)
    - **name**: Search projects by name (partial match)
    - **is_public**: Filter by public/private status
    """
    try:
        # Create filter object
        filters = ProjectFilter(
            status=status_filter, name=name_filter, is_public=is_public
        )

        projects = await project_service.get_user_projects(
            user_id=current_user.id, filters=filters, page=page, size=size
        )

        logger.info(
            f"Retrieved {len(projects.items)} projects for user {current_user.email}"
        )
        return projects

    except Exception as e:
        logger.error(f"Error retrieving projects for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve projects",
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    _: str = Depends(validate_project_exists),
) -> ProjectResponse:
    """
    Get project details by ID.

    Requires project membership or system admin privileges.
    """
    try:
        project = await project_service.get_project_by_id(project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        # Convert to response format
        project_response = ProjectResponse.model_validate(project)
        project_response.completion_rate = project.completion_rate

        return project_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project",
        )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    _: str = Depends(validate_project_exists),
) -> ProjectResponse:
    """
    Update project information.

    Requires project admin privileges.

    Only provided fields will be updated.
    """
    try:
        project = await project_service.update_project(
            project_id=project_id, project_data=project_data, user_id=current_user.id
        )

        # Convert to response format
        project_response = ProjectResponse.model_validate(project)
        project_response.completion_rate = project.completion_rate

        logger.info(f"Project updated: {project_id} by {current_user.email}")
        return project_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project",
        )


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    _: str = Depends(validate_project_exists),
) -> dict:
    """
    Delete (archive) a project.

    Only project creator or system admin can delete projects.
    This is a soft delete - the project will be marked as inactive.
    """
    try:
        success = await project_service.delete_project(project_id, current_user.id)

        if success:
            logger.info(f"Project deleted: {project_id} by {current_user.email}")
            return {
                "message": "Project deleted successfully",
                "project_id": str(project_id),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete project",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project",
        )


# Project Members Management


@router.get("/{project_id}/members", response_model=ProjectMemberListResponse)
async def get_project_members(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    active_only: bool = Query(True, description="Show only active members"),
    _: str = Depends(validate_project_exists),
) -> ProjectMemberListResponse:
    """
    Get project members with pagination.

    Requires project membership.
    """
    try:
        members = await project_service.get_project_members(
            project_id=project_id, page=page, size=size, active_only=active_only
        )

        logger.info(f"Retrieved {len(members.items)} members for project {project_id}")
        return members

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving members for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project members",
        )


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def add_project_member(
    project_id: UUID,
    member_data: ProjectMemberCreate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    _: str = Depends(validate_project_exists),
) -> dict:
    """
    Add a new member to the project.

    Requires project admin privileges.

    - **user_id**: ID of user to add as member
    - **role**: Role to assign (viewer, annotator, reviewer, project_admin)
    """
    try:
        member = await project_service.add_project_member(
            project_id=project_id, member_data=member_data, inviter_id=current_user.id
        )

        logger.info(f"Member added to project {project_id}: {member_data.user_id}")
        return {
            "message": "Member added successfully",
            "member_id": str(member.id),
            "user_id": str(member.user_id),
            "role": member.role.value,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding member to project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add project member",
        )


@router.put("/{project_id}/members/{member_id}")
async def update_project_member(
    project_id: UUID,
    member_id: UUID,
    member_data: ProjectMemberUpdate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    _: str = Depends(validate_project_exists),
) -> dict:
    """
    Update project member information.

    Requires project admin privileges.

    - **role**: New role for the member
    - **is_active**: Active status of the member
    """
    try:
        member = await project_service.update_project_member(
            project_id=project_id,
            member_id=member_id,
            member_data=member_data,
            updater_id=current_user.id,
        )

        logger.info(f"Project member updated: {member_id} in project {project_id}")
        return {
            "message": "Member updated successfully",
            "member_id": str(member.id),
            "role": member.role.value,
            "is_active": member.is_active,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating member {member_id} in project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project member",
        )


@router.delete("/{project_id}/members/{member_id}")
async def remove_project_member(
    project_id: UUID,
    member_id: UUID,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
    _: str = Depends(validate_project_exists),
) -> dict:
    """
    Remove a member from the project.

    Requires project admin privileges.
    This is a soft delete - the member will be marked as inactive.
    """
    try:
        success = await project_service.remove_project_member(
            project_id=project_id, member_id=member_id, remover_id=current_user.id
        )

        if success:
            logger.info(f"Member removed from project {project_id}: {member_id}")
            return {
                "message": "Member removed successfully",
                "member_id": str(member_id),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove project member",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error removing member {member_id} from project {project_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove project member",
        )
