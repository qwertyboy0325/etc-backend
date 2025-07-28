"""Project management service for CRUD operations and member management."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.enums import ProjectRole, ProjectStatus
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectFilter,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberListResponse,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    ProjectResponse,
    ProjectSummary,
    ProjectUpdate,
)
from app.schemas.user import UserPublic

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing projects and project members."""

    def __init__(self, db: AsyncSession):
        """Initialize project service with database session."""
        self.db = db

    async def create_project(
        self, project_data: ProjectCreate, creator_id: UUID
    ) -> Project:
        """Create a new project."""
        try:
            # Create project
            db_project = Project(
                name=project_data.name,
                description=project_data.description,
                start_date=project_data.start_date,
                end_date=project_data.end_date,
                is_public=project_data.is_public,
                max_annotations_per_task=project_data.max_annotations_per_task,
                auto_assign_tasks=project_data.auto_assign_tasks,
                require_review=project_data.require_review,
                created_by=creator_id,
                status=ProjectStatus.ACTIVE,
            )

            self.db.add(db_project)
            await self.db.flush()  # Get project ID

            # Add creator as project admin
            creator_membership = ProjectMember(
                project_id=db_project.id,
                user_id=creator_id,
                role=ProjectRole.PROJECT_ADMIN,
                is_active=True,
                joined_at=datetime.utcnow(),
                invitation_accepted_at=datetime.utcnow(),
            )

            self.db.add(creator_membership)
            await self.db.commit()
            await self.db.refresh(db_project)

            logger.info(f"Project created: {project_data.name} by {creator_id}")
            return db_project

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating project {project_data.name}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create project",
            )

    async def get_project_by_id(
        self, project_id: UUID, include_relations: bool = True
    ) -> Optional[Project]:
        """Get project by ID with optional relations."""
        try:
            query = select(Project).where(
                Project.id == project_id, Project.is_active == True
            )

            if include_relations:
                query = query.options(
                    selectinload(Project.creator),
                    selectinload(Project.members).selectinload(ProjectMember.user),
                )

            result = await self.db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error fetching project {project_id}: {e}")
            return None

    async def get_user_projects(
        self,
        user_id: UUID,
        filters: Optional[ProjectFilter] = None,
        page: int = 1,
        size: int = 50,
    ) -> ProjectListResponse:
        """Get projects for a specific user with filtering and pagination."""
        try:
            # Base query for user's projects
            query = (
                select(Project)
                .join(ProjectMember)
                .where(
                    and_(
                        ProjectMember.user_id == user_id,
                        ProjectMember.is_active == True,
                        Project.is_active == True,
                    )
                )
                .options(selectinload(Project.creator))
            )

            # Apply filters
            if filters:
                if filters.status:
                    query = query.where(Project.status == filters.status)
                if filters.is_public is not None:
                    query = query.where(Project.is_public == filters.is_public)
                if filters.name:
                    query = query.where(Project.name.ilike(f"%{filters.name}%"))
                if filters.start_date_from:
                    query = query.where(Project.start_date >= filters.start_date_from)
                if filters.start_date_to:
                    query = query.where(Project.start_date <= filters.start_date_to)

            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            offset = (page - 1) * size
            query = query.offset(offset).limit(size).order_by(Project.created_at.desc())

            # Execute query
            result = await self.db.execute(query)
            projects = result.scalars().all()

            # Convert to response format
            project_responses = []
            for project in projects:
                project_response = ProjectResponse.model_validate(project)
                project_response.completion_rate = project.completion_rate
                if project.creator:
                    project_response.creator = UserPublic.model_validate(
                        project.creator
                    )
                project_responses.append(project_response)

            pages = (total + size - 1) // size

            return ProjectListResponse(
                items=project_responses, total=total, page=page, size=size, pages=pages
            )

        except Exception as e:
            logger.error(f"Error fetching user projects for {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch projects",
            )

    async def update_project(
        self, project_id: UUID, project_data: ProjectUpdate, user_id: UUID
    ) -> Project:
        """Update project information."""
        project = await self.get_project_by_id(project_id, include_relations=False)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        # Check permissions
        if not await self._user_can_manage_project(user_id, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update project",
            )

        try:
            # Update fields
            update_data = project_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(project, field, value)

            project.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(project)

            logger.info(f"Project updated: {project_id} by {user_id}")
            return project

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating project {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update project",
            )

    async def delete_project(self, project_id: UUID, user_id: UUID) -> bool:
        """Soft delete a project (mark as inactive)."""
        project = await self.get_project_by_id(project_id, include_relations=False)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        # Check permissions (only project creator, admin, or system admin can delete)
        if project.created_by != user_id:
            # Check if user is admin or system admin
            user = await self.db.get(User, user_id)
            if not user or (not user.is_admin and not user.is_system_admin):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only project creator, admin, or system admin can delete project",
                )

        try:
            project.is_active = False
            project.status = ProjectStatus.ARCHIVED
            project.updated_at = datetime.utcnow()
            await self.db.commit()

            logger.info(f"Project deleted: {project_id} by {user_id}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting project {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete project",
            )

    async def add_project_member(
        self, project_id: UUID, member_data: ProjectMemberCreate, inviter_id: UUID
    ) -> ProjectMember:
        """Add a new member to the project."""
        # Check if project exists
        project = await self.get_project_by_id(project_id, include_relations=False)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        # Check if inviter has permission
        if not await self._user_can_manage_members(inviter_id, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to add members",
            )

        # Check if user exists
        user = await self.db.get(User, member_data.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if user is already a member
        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == member_data.user_id,
            )
        )
        existing_member = result.scalar_one_or_none()

        if existing_member:
            if existing_member.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User is already a member of this project",
                )
            else:
                # Reactivate membership
                existing_member.is_active = True
                existing_member.role = member_data.role
                existing_member.invited_by = inviter_id
                existing_member.invitation_accepted_at = datetime.utcnow()
                existing_member.updated_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(existing_member)
                return existing_member

        try:
            # Create new membership
            new_member = ProjectMember(
                project_id=project_id,
                user_id=member_data.user_id,
                role=member_data.role,
                invited_by=inviter_id,
                invitation_accepted_at=datetime.utcnow(),
                is_active=True,
            )

            self.db.add(new_member)
            await self.db.commit()
            await self.db.refresh(new_member)

            logger.info(f"Member added to project {project_id}: {member_data.user_id}")
            return new_member

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error adding member to project {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add project member",
            )

    async def update_project_member(
        self,
        project_id: UUID,
        member_id: UUID,
        member_data: ProjectMemberUpdate,
        updater_id: UUID,
    ) -> ProjectMember:
        """Update project member information."""
        # Get member
        result = await self.db.execute(
            select(ProjectMember)
            .options(selectinload(ProjectMember.user))
            .where(
                ProjectMember.id == member_id, ProjectMember.project_id == project_id
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found"
            )

        # Check permissions
        if not await self._user_can_manage_members(updater_id, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update member",
            )

        try:
            # Update fields
            update_data = member_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(member, field, value)

            member.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(member)

            logger.info(f"Project member updated: {member_id} in project {project_id}")
            return member

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating project member {member_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update project member",
            )

    async def remove_project_member(
        self, project_id: UUID, member_id: UUID, remover_id: UUID
    ) -> bool:
        """Remove a member from the project."""
        # Get member
        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.id == member_id, ProjectMember.project_id == project_id
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found"
            )

        # Check permissions
        if not await self._user_can_manage_members(remover_id, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to remove member",
            )

        try:
            member.is_active = False
            member.left_at = datetime.utcnow()
            member.updated_at = datetime.utcnow()
            await self.db.commit()

            logger.info(
                f"Project member removed: {member_id} from project {project_id}"
            )
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error removing project member {member_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove project member",
            )

    async def get_project_members(
        self, project_id: UUID, page: int = 1, size: int = 50, active_only: bool = True
    ) -> ProjectMemberListResponse:
        """Get project members with pagination."""
        # Verify project exists
        project = await self.get_project_by_id(project_id, include_relations=False)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        try:
            # Base query
            query = (
                select(ProjectMember)
                .options(selectinload(ProjectMember.user))
                .where(ProjectMember.project_id == project_id)
            )

            if active_only:
                query = query.where(ProjectMember.is_active == True)

            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            offset = (page - 1) * size
            query = (
                query.offset(offset)
                .limit(size)
                .order_by(ProjectMember.joined_at.desc())
            )

            # Execute query
            result = await self.db.execute(query)
            members = result.scalars().all()

            # Convert to response format
            member_responses = []
            for member in members:
                member_response = ProjectMemberResponse.model_validate(member)
                if member.user:
                    member_response.user = UserPublic.model_validate(member.user)
                member_responses.append(member_response)

            pages = (total + size - 1) // size

            return ProjectMemberListResponse(
                items=member_responses, total=total, page=page, size=size, pages=pages
            )

        except Exception as e:
            logger.error(f"Error fetching project members for {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch project members",
            )

    async def _user_can_manage_project(self, user_id: UUID, project_id: UUID) -> bool:
        """Check if user can manage project (admin or creator)."""
        # Check if user is project admin or creator
        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
                ProjectMember.is_active == True,
                ProjectMember.role == ProjectRole.PROJECT_ADMIN,
            )
        )
        membership = result.scalar_one_or_none()

        if membership:
            return True

        # Check if user is project creator
        project = await self.db.get(Project, project_id)
        if project and project.created_by == user_id:
            return True

        return False

    async def _user_can_manage_members(self, user_id: UUID, project_id: UUID) -> bool:
        """Check if user can manage project members."""
        return await self._user_can_manage_project(user_id, project_id)
