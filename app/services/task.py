"""Task management service for creating, assigning, and tracking annotation tasks."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import TaskPriority, TaskStatus
from app.models.pointcloud import PointCloudFile
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskAssignment,
    TaskCreate,
    TaskFilter,
    TaskListResponse,
    TaskResponse,
    TaskStats,
    TaskSummary,
    TaskUpdate,
)

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing annotation tasks."""

    def __init__(self, db: AsyncSession):
        """Initialize task service with database session."""
        self.db = db

    async def create_task(
        self, task_data: TaskCreate, creator_id: UUID, project_id: UUID
    ) -> Task:
        """Create a new annotation task."""
        try:
            # Verify point cloud file exists and belongs to project
            pointcloud_file = await self.db.get(
                PointCloudFile, task_data.pointcloud_file_id
            )
            if not pointcloud_file or pointcloud_file.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Point cloud file not found in this project",
                )

            if not pointcloud_file.can_create_tasks():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create tasks for this file (not processed or no points)",
                )

            # Create task
            db_task = Task(
                project_id=project_id,
                name=task_data.name,
                description=task_data.description,
                pointcloud_file_id=task_data.pointcloud_file_id,
                priority=task_data.priority or TaskPriority.MEDIUM,
                max_annotations=task_data.max_annotations or 3,
                require_review=(
                    task_data.require_review
                    if task_data.require_review is not None
                    else True
                ),
                due_date=task_data.due_date,
                instructions=task_data.instructions,
                created_by=creator_id,
                status=TaskStatus.PENDING,
            )

            self.db.add(db_task)
            await self.db.commit()
            await self.db.refresh(db_task)

            logger.info(f"Task created: {task_data.name} by {creator_id}")
            return db_task

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating task {task_data.name}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create task",
            )

    async def get_task_by_id(
        self, task_id: UUID, include_relations: bool = True
    ) -> Optional[Task]:
        """Get task by ID with optional relations."""
        try:
            query = select(Task).where(Task.id == task_id)

            if include_relations:
                query = query.options(
                    selectinload(Task.creator),
                    selectinload(Task.assignee),
                    selectinload(Task.pointcloud_file),
                    selectinload(Task.annotations),
                )

            result = await self.db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error fetching task {task_id}: {e}")
            return None

    async def get_project_tasks(
        self,
        project_id: UUID,
        filters: Optional[TaskFilter] = None,
        page: int = 1,
        size: int = 50,
    ) -> TaskListResponse:
        """Get tasks for a project with filtering and pagination."""
        try:
            # Base query for project tasks
            query = (
                select(Task)
                .where(Task.project_id == project_id)
                .options(
                    selectinload(Task.creator),
                    selectinload(Task.assignee),
                    selectinload(Task.pointcloud_file),
                )
            )

            # Apply filters
            if filters:
                if filters.status:
                    query = query.where(Task.status == filters.status)
                if filters.priority:
                    query = query.where(Task.priority == filters.priority)
                if filters.assigned_to:
                    query = query.where(Task.assigned_to == filters.assigned_to)
                if filters.created_by:
                    query = query.where(Task.created_by == filters.created_by)
                if filters.name:
                    query = query.where(Task.name.ilike(f"%{filters.name}%"))
                if filters.overdue_only:
                    query = query.where(
                        and_(
                            Task.due_date.isnot(None),
                            Task.due_date < datetime.utcnow(),
                            Task.status.notin_(
                                [
                                    TaskStatus.COMPLETED,
                                    TaskStatus.REVIEWED,
                                    TaskStatus.CANCELLED,
                                ]
                            ),
                        )
                    )

            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            offset = (page - 1) * size
            query = query.offset(offset).limit(size).order_by(Task.created_at.desc())

            # Execute query
            result = await self.db.execute(query)
            tasks = result.scalars().all()

            # Convert to response format
            task_responses = [TaskResponse.model_validate(task) for task in tasks]

            pages = (total + size - 1) // size

            return TaskListResponse(
                items=task_responses, total=total, page=page, size=size, pages=pages
            )

        except Exception as e:
            logger.error(f"Error fetching tasks for project {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch tasks",
            )

    async def get_user_tasks(
        self,
        user_id: UUID,
        project_id: Optional[UUID] = None,
        status_filter: Optional[TaskStatus] = None,
        page: int = 1,
        size: int = 50,
    ) -> TaskListResponse:
        """Get tasks assigned to a specific user."""
        try:
            query = (
                select(Task)
                .where(Task.assigned_to == user_id)
                .options(
                    selectinload(Task.creator),
                    selectinload(Task.pointcloud_file),
                )
            )

            if project_id:
                query = query.where(Task.project_id == project_id)

            if status_filter:
                query = query.where(Task.status == status_filter)

            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            offset = (page - 1) * size
            query = query.offset(offset).limit(size).order_by(Task.created_at.desc())

            # Execute query
            result = await self.db.execute(query)
            tasks = result.scalars().all()

            # Convert to response format
            task_responses = [TaskResponse.model_validate(task) for task in tasks]

            pages = (total + size - 1) // size

            return TaskListResponse(
                items=task_responses, total=total, page=page, size=size, pages=pages
            )

        except Exception as e:
            logger.error(f"Error fetching user tasks for {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch user tasks",
            )

    async def update_task(
        self, task_id: UUID, task_data: TaskUpdate, user_id: UUID
    ) -> Task:
        """Update task information."""
        task = await self.get_task_by_id(task_id, include_relations=False)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        # Check permissions (creator or project admin)
        if not await self._user_can_manage_task(user_id, task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update task",
            )

        try:
            # Update fields
            update_data = task_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(task, field, value)

            task.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(task)

            logger.info(f"Task updated: {task_id} by {user_id}")
            return task

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update task",
            )

    async def assign_task(
        self, task_id: UUID, assignee_id: UUID, assigner_id: UUID
    ) -> Task:
        """Assign a task to a user."""
        task = await self.get_task_by_id(task_id, include_relations=False)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        if task.status != TaskStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task cannot be assigned in current status",
            )

        # Check if assigner has permission
        if not await self._user_can_manage_task(assigner_id, task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to assign task",
            )

        # Check if assignee is a project member
        if not await self._user_can_work_on_task(assignee_id, task.project_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not a member of this project or lacks required permissions",
            )

        # Check assignee workload
        current_load = await self._get_user_active_task_count(assignee_id)
        if current_load >= 10:  # Maximum concurrent tasks
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has too many active tasks",
            )

        try:
            task.assign_to_user(str(assignee_id))
            await self.db.commit()
            await self.db.refresh(task)

            logger.info(f"Task {task_id} assigned to {assignee_id} by {assigner_id}")
            return task

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error assigning task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to assign task",
            )

    async def unassign_task(self, task_id: UUID, user_id: UUID) -> Task:
        """Unassign a task from its current assignee."""
        task = await self.get_task_by_id(task_id, include_relations=False)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        if task.status not in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task cannot be unassigned in current status",
            )

        # Check permissions (assignee can unassign themselves, or manager can unassign)
        if task.assigned_to != user_id and not await self._user_can_manage_task(
            user_id, task
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to unassign task",
            )

        try:
            task.assigned_to = None
            task.assigned_at = None
            task.status = TaskStatus.PENDING
            task.updated_at = datetime.utcnow()

            await self.db.commit()
            await self.db.refresh(task)

            logger.info(f"Task {task_id} unassigned by {user_id}")
            return task

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error unassigning task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unassign task",
            )

    async def update_task_status(
        self, task_id: UUID, new_status: TaskStatus, user_id: UUID
    ) -> Task:
        """Update task status."""
        task = await self.get_task_by_id(task_id, include_relations=False)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        # Check permissions
        if new_status == TaskStatus.IN_PROGRESS:
            # Only assignee can mark as in progress
            if task.assigned_to != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only assignee can start task",
                )
            if task.status != TaskStatus.ASSIGNED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task must be assigned before starting",
                )
        elif new_status == TaskStatus.COMPLETED:
            # Only assignee can mark as completed
            if task.assigned_to != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only assignee can complete task",
                )
            if task.status != TaskStatus.IN_PROGRESS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task must be in progress before completing",
                )
        elif new_status in [
            TaskStatus.REVIEWED,
            TaskStatus.REJECTED,
            TaskStatus.CANCELLED,
        ]:
            # Only project managers can set these statuses
            if not await self._user_can_manage_task(user_id, task):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to set this status",
                )

        try:
            # Update status using model methods
            if new_status == TaskStatus.IN_PROGRESS:
                task.mark_in_progress()
            elif new_status == TaskStatus.COMPLETED:
                task.mark_completed()
            else:
                task.status = new_status
                task.updated_at = datetime.utcnow()

            await self.db.commit()
            await self.db.refresh(task)

            logger.info(f"Task {task_id} status updated to {new_status} by {user_id}")
            return task

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating task status {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update task status",
            )

    async def auto_assign_task(self, project_id: UUID, user_id: UUID) -> Optional[Task]:
        """Automatically assign the next available task to a user."""
        try:
            # Check if user can work on tasks in this project
            if not await self._user_can_work_on_task(user_id, project_id):
                return None

            # Check user's current workload
            current_load = await self._get_user_active_task_count(user_id)
            if current_load >= 5:  # Lower limit for auto-assignment
                return None

            # Find next available task
            query = (
                select(Task)
                .where(
                    and_(
                        Task.project_id == project_id,
                        Task.status == TaskStatus.PENDING,
                        Task.assigned_to.is_(None),
                    )
                )
                .order_by(Task.priority.desc(), Task.created_at.asc())
                .limit(1)
            )

            result = await self.db.execute(query)
            task = result.scalar_one_or_none()

            if task:
                task.assign_to_user(str(user_id))
                await self.db.commit()
                await self.db.refresh(task)
                logger.info(f"Task {task.id} auto-assigned to {user_id}")

            return task

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error auto-assigning task for user {user_id}: {e}")
            return None

    async def get_task_stats(self, project_id: UUID) -> TaskStats:
        """Get task statistics for a project."""
        try:
            # Count tasks by status
            status_counts = {}
            for status in TaskStatus:
                count_query = select(func.count()).where(
                    and_(Task.project_id == project_id, Task.status == status)
                )
                result = await self.db.execute(count_query)
                status_counts[status.value] = result.scalar()

            # Get overdue tasks count
            overdue_query = select(func.count()).where(
                and_(
                    Task.project_id == project_id,
                    Task.due_date.isnot(None),
                    Task.due_date < datetime.utcnow(),
                    Task.status.notin_(
                        [
                            TaskStatus.COMPLETED,
                            TaskStatus.REVIEWED,
                            TaskStatus.CANCELLED,
                        ]
                    ),
                )
            )
            overdue_result = await self.db.execute(overdue_query)
            overdue_count = overdue_result.scalar()

            # Calculate completion rate
            total_tasks = sum(status_counts.values())
            completed_tasks = status_counts.get("completed", 0) + status_counts.get(
                "reviewed", 0
            )
            completion_rate = (
                (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            )

            return TaskStats(
                total_tasks=total_tasks,
                pending_tasks=status_counts.get("pending", 0),
                assigned_tasks=status_counts.get("assigned", 0),
                in_progress_tasks=status_counts.get("in_progress", 0),
                completed_tasks=completed_tasks,
                overdue_tasks=overdue_count,
                completion_rate=round(completion_rate, 2),
                status_breakdown=status_counts,
            )

        except Exception as e:
            logger.error(f"Error getting task stats for project {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get task statistics",
            )

    async def delete_task(self, task_id: UUID, user_id: UUID) -> bool:
        """Delete a task (soft delete by cancelling)."""
        task = await self.get_task_by_id(task_id, include_relations=False)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        # Check permissions (only creator or project admin can delete)
        if not await self._user_can_manage_task(user_id, task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete task",
            )

        if task.status in [TaskStatus.COMPLETED, TaskStatus.REVIEWED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete completed tasks",
            )

        try:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.utcnow()
            await self.db.commit()

            logger.info(f"Task deleted: {task_id} by {user_id}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete task",
            )

    # Helper methods

    async def _user_can_manage_task(self, user_id: UUID, task: Task) -> bool:
        """Check if user can manage task (creator or project admin)."""
        # Check if user is task creator
        if task.created_by == user_id:
            return True

        # Check if user is project admin
        from app.models.enums import ProjectRole

        query = select(ProjectMember).where(
            and_(
                ProjectMember.project_id == task.project_id,
                ProjectMember.user_id == user_id,
                ProjectMember.is_active == True,
                ProjectMember.role == ProjectRole.PROJECT_ADMIN,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _user_can_work_on_task(self, user_id: UUID, project_id: UUID) -> bool:
        """Check if user can work on tasks in this project."""
        from app.models.enums import ProjectRole

        query = select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
                ProjectMember.is_active == True,
                ProjectMember.role.in_(
                    [
                        ProjectRole.ANNOTATOR,
                        ProjectRole.REVIEWER,
                        ProjectRole.PROJECT_ADMIN,
                    ]
                ),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _get_user_active_task_count(self, user_id: UUID) -> int:
        """Get count of active tasks for a user."""
        query = select(func.count()).where(
            and_(
                Task.assigned_to == user_id,
                Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]),
            )
        )
        result = await self.db.execute(query)
        return result.scalar()
