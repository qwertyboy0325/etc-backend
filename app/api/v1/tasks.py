"""Task management API endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_db,
    require_project_access,
    validate_project_exists,
)
from app.core.database import get_db
from app.models.enums import ProjectRole, TaskPriority, TaskStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.task import (
    TaskAssignment,
    TaskCreate,
    TaskFilter,
    TaskListResponse,
    TaskResponse,
    TaskStats,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services.task import TaskService

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    """Get task service instance."""
    return TaskService(db)


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new task",
    description="Create a new annotation task in a project.",
)
async def create_task(
    project_id: UUID,
    task_data: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.PROJECT_ADMIN)),
) -> TaskResponse:
    """
    Create a new annotation task.

    **Required permissions**: Project ADMIN

    **Parameters**:
    - **name**: Task name (required)
    - **description**: Optional task description
    - **pointcloud_file_id**: Point cloud file to annotate (required)
    - **priority**: Task priority (low, medium, high, urgent)
    - **max_annotations**: Maximum annotations per task (1-10, default: 3)
    - **require_review**: Whether annotations require review (default: true)
    - **due_date**: Optional due date
    - **instructions**: Special instructions for annotators
    """
    try:
        task = await task_service.create_task(
            task_data=task_data, creator_id=current_user.id, project_id=project_id
        )

        task_response = TaskResponse.model_validate(task)
        logger.info(f"Task created successfully: {task.name} by {current_user.email}")
        return task_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task creation failed",
        )


@router.get(
    "/projects/{project_id}/tasks",
    response_model=TaskListResponse,
    summary="List project tasks",
    description="Get paginated list of tasks in a project with filtering options.",
)
async def list_project_tasks(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.VIEWER)),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    status_filter: Optional[TaskStatus] = Query(None, description="Filter by status"),
    priority_filter: Optional[TaskPriority] = Query(
        None, description="Filter by priority"
    ),
    assigned_to: Optional[UUID] = Query(None, description="Filter by assignee"),
    created_by: Optional[UUID] = Query(None, description="Filter by creator"),
    name_search: Optional[str] = Query(None, description="Search by task name"),
    overdue_only: bool = Query(False, description="Show only overdue tasks"),
) -> TaskListResponse:
    """
    Get paginated list of tasks in a project.

    **Required permissions**: Project VIEWER or higher

    **Query parameters**:
    - **page**: Page number (starting from 1)
    - **size**: Items per page (1-100)
    - **status_filter**: Filter by task status
    - **priority_filter**: Filter by task priority
    - **assigned_to**: Filter by assignee user ID
    - **created_by**: Filter by creator user ID
    - **name_search**: Search tasks by name (partial match)
    - **overdue_only**: Show only overdue tasks
    """
    try:
        # Create filter object
        filters = TaskFilter(
            status=status_filter,
            priority=priority_filter,
            assigned_to=assigned_to,
            created_by=created_by,
            name=name_search,
            overdue_only=overdue_only,
        )

        tasks = await task_service.get_project_tasks(
            project_id=project_id, filters=filters, page=page, size=size
        )

        logger.info(f"Retrieved {len(tasks.items)} tasks for project {project_id}")
        return tasks

    except Exception as e:
        logger.error(f"Error retrieving tasks for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tasks",
        )


@router.get(
    "/projects/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get task details",
    description="Get detailed information about a specific task.",
)
async def get_task(
    project_id: UUID,
    task_id: UUID,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.VIEWER)),
) -> TaskResponse:
    """
    Get detailed information about a specific task.

    **Required permissions**: Project VIEWER or higher
    """
    try:
        task = await task_service.get_task_by_id(task_id)

        if not task or task.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        task_response = TaskResponse.model_validate(task)
        return task_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task",
        )


@router.put(
    "/projects/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Update task",
    description="Update task information.",
)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.ANNOTATOR)),
) -> TaskResponse:
    """
    Update task information.

    **Required permissions**: Task creator or project ADMIN

    Only provided fields will be updated.
    """
    try:
        task = await task_service.update_task(
            task_id=task_id, task_data=task_data, user_id=current_user.id
        )

        if task.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        task_response = TaskResponse.model_validate(task)
        logger.info(f"Task updated: {task_id} by {current_user.email}")
        return task_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task",
        )


@router.delete(
    "/projects/{project_id}/tasks/{task_id}",
    summary="Delete task",
    description="Delete (cancel) a task.",
)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.ANNOTATOR)),
) -> dict:
    """
    Delete (cancel) a task.

    **Required permissions**: Task creator or project ADMIN

    This is a soft delete - the task will be marked as cancelled.
    Completed tasks cannot be deleted.
    """
    try:
        success = await task_service.delete_task(task_id, current_user.id)

        if success:
            logger.info(f"Task deleted: {task_id} by {current_user.email}")
            return {
                "message": "Task deleted successfully",
                "task_id": str(task_id),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete task",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete task",
        )


# Task Assignment Endpoints


@router.post(
    "/projects/{project_id}/tasks/{task_id}/assign",
    response_model=TaskResponse,
    summary="Assign task",
    description="Assign a task to a user.",
)
async def assign_task(
    project_id: UUID,
    task_id: UUID,
    assignment_data: TaskAssignment,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.REVIEWER)),
) -> TaskResponse:
    """
    Assign a task to a user.

    **Required permissions**: Project REVIEWER or higher

    **Parameters**:
    - **assignee_id**: User ID to assign the task to

    **Requirements**:
    - Task must be in PENDING status
    - Assignee must be a project member with ANNOTATOR role or higher
    - Assignee cannot have more than 10 active tasks
    """
    try:
        task = await task_service.assign_task(
            task_id=task_id,
            assignee_id=assignment_data.assignee_id,
            assigner_id=current_user.id,
        )

        if task.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        task_response = TaskResponse.model_validate(task)
        logger.info(
            f"Task {task_id} assigned to {assignment_data.assignee_id} by {current_user.email}"
        )
        return task_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign task",
        )


@router.post(
    "/projects/{project_id}/tasks/{task_id}/unassign",
    response_model=TaskResponse,
    summary="Unassign task",
    description="Unassign a task from its current assignee.",
)
async def unassign_task(
    project_id: UUID,
    task_id: UUID,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.ANNOTATOR)),
) -> TaskResponse:
    """
    Unassign a task from its current assignee.

    **Required permissions**:
    - Task assignee (can unassign themselves)
    - Project REVIEWER or higher (can unassign any task)

    **Requirements**:
    - Task must be in ASSIGNED or IN_PROGRESS status
    """
    try:
        task = await task_service.unassign_task(
            task_id=task_id, user_id=current_user.id
        )

        if task.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        task_response = TaskResponse.model_validate(task)
        logger.info(f"Task {task_id} unassigned by {current_user.email}")
        return task_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unassigning task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unassign task",
        )


@router.post(
    "/projects/{project_id}/tasks/auto-assign",
    response_model=Optional[TaskResponse],
    summary="Auto-assign task",
    description="Automatically assign the next available task to the current user.",
)
async def auto_assign_task(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.ANNOTATOR)),
) -> Optional[TaskResponse]:
    """
    Automatically assign the next available task to the current user.

    **Required permissions**: Project ANNOTATOR or higher

    **Logic**:
    - Finds the next pending task with highest priority
    - Checks user's current workload (max 5 tasks for auto-assignment)
    - Assigns task if available and user is eligible

    **Returns**:
    - Task details if assignment successful
    - null if no tasks available or user has too many active tasks
    """
    try:
        task = await task_service.auto_assign_task(
            project_id=project_id, user_id=current_user.id
        )

        if task:
            task_response = TaskResponse.model_validate(task)
            logger.info(f"Task {task.id} auto-assigned to {current_user.email}")
            return task_response
        else:
            logger.info(
                f"No tasks available for auto-assignment to {current_user.email}"
            )
            return None

    except Exception as e:
        logger.error(f"Error auto-assigning task for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to auto-assign task",
        )


# Task Status Management


@router.post(
    "/projects/{project_id}/tasks/{task_id}/status",
    response_model=TaskResponse,
    summary="Update task status",
    description="Update the status of a task.",
)
async def update_task_status(
    project_id: UUID,
    task_id: UUID,
    status_data: TaskStatusUpdate,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.ANNOTATOR)),
) -> TaskResponse:
    """
    Update the status of a task.

    **Required permissions**: Varies by status
    - IN_PROGRESS: Only task assignee
    - COMPLETED: Only task assignee
    - REVIEWED/REJECTED/CANCELLED: Project REVIEWER or higher

    **Status flow**:
    - PENDING → ASSIGNED (via assignment)
    - ASSIGNED → IN_PROGRESS (assignee starts work)
    - IN_PROGRESS → COMPLETED (assignee finishes work)
    - COMPLETED → REVIEWED (reviewer approves)
    - Any → CANCELLED (admin cancels)
    - COMPLETED → REJECTED (reviewer rejects)
    """
    try:
        task = await task_service.update_task_status(
            task_id=task_id, new_status=status_data.status, user_id=current_user.id
        )

        if task.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        task_response = TaskResponse.model_validate(task)
        logger.info(
            f"Task {task_id} status updated to {status_data.status} by {current_user.email}"
        )
        return task_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task status {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task status",
        )


# User Tasks Endpoints


@router.get(
    "/users/me/tasks",
    response_model=TaskListResponse,
    summary="Get my tasks",
    description="Get tasks assigned to the current user.",
)
async def get_my_tasks(
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
    status_filter: Optional[TaskStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
) -> TaskListResponse:
    """
    Get tasks assigned to the current user.

    **Query parameters**:
    - **project_id**: Filter by specific project
    - **status_filter**: Filter by task status
    - **page**: Page number (starting from 1)
    - **size**: Items per page (1-100)
    """
    try:
        tasks = await task_service.get_user_tasks(
            user_id=current_user.id,
            project_id=project_id,
            status_filter=status_filter,
            page=page,
            size=size,
        )

        logger.info(f"Retrieved {len(tasks.items)} tasks for user {current_user.email}")
        return tasks

    except Exception as e:
        logger.error(f"Error retrieving tasks for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user tasks",
        )


# Statistics Endpoints


@router.get(
    "/projects/{project_id}/tasks/stats",
    response_model=TaskStats,
    summary="Get task statistics",
    description="Get task statistics for a project.",
)
async def get_task_stats(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.VIEWER)),
) -> TaskStats:
    """
    Get task statistics for a project.

    **Required permissions**: Project VIEWER or higher

    **Returns**:
    - Total tasks count
    - Tasks by status breakdown
    - Overdue tasks count
    - Overall completion rate
    """
    try:
        stats = await task_service.get_task_stats(project_id=project_id)

        logger.info(f"Retrieved task stats for project {project_id}")
        return stats

    except Exception as e:
        logger.error(f"Error retrieving task stats for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task statistics",
        )
