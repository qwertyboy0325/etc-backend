"""API dependencies for authentication and authorization."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import GlobalRole, ProjectRole
from app.models.user import User
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Get authentication service instance."""
    return AuthService(db)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    user = await auth_service.get_current_user(credentials.credentials)
    if not user:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current verified user."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email not verified"
        )
    return current_user


def require_global_role(required_role: GlobalRole):
    """Dependency factory for global role requirements."""

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.global_role == GlobalRole.SYSTEM_ADMIN:
            return current_user  # System admin can access everything

        if (
            required_role == GlobalRole.ADMIN
            and current_user.global_role != GlobalRole.ADMIN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )

        return current_user

    return role_checker


def require_admin():
    """Require admin privileges."""
    return require_global_role(GlobalRole.ADMIN)


def require_system_admin():
    """Require system admin privileges."""
    return require_global_role(GlobalRole.SYSTEM_ADMIN)


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if not credentials:
        return None

    try:
        user = await auth_service.get_current_user(credentials.credentials)
        return user
    except Exception:
        return None


class ProjectPermissionChecker:
    """Check project-level permissions."""

    def __init__(self, required_role: ProjectRole = None, require_active: bool = True):
        self.required_role = required_role
        self.require_active = require_active

    async def __call__(
        self,
        project_id: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        """Check if user has required role in project."""
        from sqlalchemy.future import select

        from app.models.project import ProjectMember

        # System admins and admins can access everything
        if current_user.global_role in [GlobalRole.SYSTEM_ADMIN, GlobalRole.ADMIN]:
            return current_user

        # Check project membership
        result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied",
            )

        if self.require_active and not membership.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project membership is inactive",
            )

        # Check role requirements
        if self.required_role:
            # Define role hierarchy
            role_hierarchy = {
                ProjectRole.VIEWER: 0,
                ProjectRole.ANNOTATOR: 1,
                ProjectRole.REVIEWER: 2,
                ProjectRole.PROJECT_ADMIN: 3,
            }

            user_role_level = role_hierarchy.get(membership.role, -1)
            required_role_level = role_hierarchy.get(self.required_role, 999)

            if user_role_level < required_role_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role {self.required_role.value} or higher required",
                )

        return current_user


# Convenience functions for common permission checks
def require_project_access(project_id: str = None):
    """Require access to project (any role)."""
    return ProjectPermissionChecker()


def require_project_annotator(project_id: str = None):
    """Require annotator role or higher in project."""
    return ProjectPermissionChecker(ProjectRole.ANNOTATOR)


def require_project_reviewer(project_id: str = None):
    """Require reviewer role or higher in project."""
    return ProjectPermissionChecker(ProjectRole.REVIEWER)


def require_project_admin(project_id: str = None):
    """Require project admin role."""
    return ProjectPermissionChecker(ProjectRole.PROJECT_ADMIN)


async def validate_project_exists(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> str:
    """Validate that project exists and return project ID."""
    from sqlalchemy.future import select

    from app.models.project import Project

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.is_active == True)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    return project_id
