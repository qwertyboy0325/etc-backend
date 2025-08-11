"""Vehicle types API endpoints for projects."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_db,
    require_project_access,
    validate_project_exists,
)
from app.models.enums import ProjectRole
from app.models.project import Project
from app.models.user import User
from app.models.vehicle_type import ProjectVehicleType
from app.schemas.annotation import VehicleTypeInfo

router = APIRouter()


@router.get(
    "/projects/{project_id}/vehicle-types",
    response_model=List[VehicleTypeInfo],
    summary="List vehicle types for a project",
    description="Get all vehicle types available within the specified project.",
)
async def list_project_vehicle_types(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Project = Depends(validate_project_exists),
    __: bool = Depends(require_project_access(ProjectRole.VIEWER)),
) -> List[VehicleTypeInfo]:
    """Return vehicle types configured for the given project."""
    try:
        result = await db.execute(
            select(ProjectVehicleType).where(
                ProjectVehicleType.project_id == project_id
            )
        )
        items = result.scalars().all()
        return [VehicleTypeInfo.model_validate(vt) for vt in items]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list vehicle types: {str(e)}",
        )
