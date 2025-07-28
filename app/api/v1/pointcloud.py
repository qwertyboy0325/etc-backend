"""Point cloud file management API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_db,
    require_project_access,
    validate_project_exists,
)
from app.models.enums import FileStatus, ProjectRole
from app.models.project import Project
from app.models.user import User
from app.schemas.pointcloud import (
    FileDownloadResponse,
    FileUploadResponse,
    PointCloudFileListResponse,
    PointCloudFileResponse,
    PointCloudFileSummary,
    PointCloudStats,
)
from app.services.file_upload import FileUploadService

router = APIRouter()


@router.post(
    "/projects/{project_id}/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload point cloud file",
    description="Upload a point cloud file to a project. Supports .npy, .npz, .ply, and .pcd formats.",
)
async def upload_pointcloud_file(
    project_id: UUID,
    file: UploadFile = File(..., description="Point cloud file to upload"),
    description: Optional[str] = Form(None, description="Optional file description"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.ANNOTATOR)),
) -> FileUploadResponse:
    """
    Upload a point cloud file to a project.

    **Required permissions**: Project ANNOTATOR or higher

    **Supported formats**:
    - .npy (NumPy array format)
    - .npz (Compressed NumPy arrays)
    - .ply (Stanford PLY format)
    - .pcd (Point Cloud Data format)

    **File size limit**: 50MB (configurable)

    The file will be automatically analyzed to extract metadata such as:
    - Point count
    - Bounding box
    - Data dimensions
    - Basic quality assessment
    """
    upload_service = FileUploadService(db)

    try:
        pointcloud_file = await upload_service.upload_pointcloud(
            file=file,
            project_id=project_id,
            uploaded_by=current_user.id,
            description=description,
        )

        return FileUploadResponse(
            file_id=pointcloud_file.id,
            filename=pointcloud_file.filename,
            original_filename=pointcloud_file.original_filename,
            file_size=pointcloud_file.file_size,
            status=pointcloud_file.status,
            point_count=pointcloud_file.point_count,
            bounding_box=pointcloud_file.bounding_box,
            checksum=pointcloud_file.checksum or "",
            message="File uploaded and analyzed successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/files",
    response_model=PointCloudFileListResponse,
    summary="List project files",
    description="Get a paginated list of point cloud files in a project.",
)
async def list_project_files(
    project_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    status_filter: Optional[FileStatus] = Query(
        None, description="Filter by file status"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.VIEWER)),
) -> PointCloudFileListResponse:
    """
    Get a paginated list of point cloud files in a project.

    **Required permissions**: Project VIEWER or higher
    """
    upload_service = FileUploadService(db)

    skip = (page - 1) * size
    files = await upload_service.get_project_files(
        project_id=project_id,
        skip=skip,
        limit=size,
        status_filter=status_filter,
    )

    # Get total count (simplified - in production you might want a more efficient count)
    total_files = await upload_service.get_project_files(
        project_id=project_id, skip=0, limit=1000
    )
    total = len(total_files)

    file_summaries = [
        PointCloudFileSummary(
            id=f.id,
            original_filename=f.original_filename,
            file_size=f.file_size,
            status=f.status,
            point_count=f.point_count,
            upload_completed_at=f.upload_completed_at,
            created_at=f.created_at,
        )
        for f in files
    ]

    pages = (total + size - 1) // size  # Ceiling division

    return PointCloudFileListResponse(
        items=file_summaries,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/projects/{project_id}/files/{file_id}",
    response_model=PointCloudFileResponse,
    summary="Get file details",
    description="Get detailed information about a specific point cloud file.",
)
async def get_file_details(
    project_id: UUID,
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.VIEWER)),
) -> PointCloudFileResponse:
    """
    Get detailed information about a specific point cloud file.

    **Required permissions**: Project VIEWER or higher
    """
    upload_service = FileUploadService(db)

    pointcloud_file = await upload_service.get_file_by_id(file_id)
    if not pointcloud_file or pointcloud_file.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    return PointCloudFileResponse.model_validate(pointcloud_file)


@router.get(
    "/projects/{project_id}/files/{file_id}/download",
    response_model=FileDownloadResponse,
    summary="Get download URL",
    description="Generate a temporary download URL for a point cloud file.",
)
async def get_file_download_url(
    project_id: UUID,
    file_id: UUID,
    expires_in_hours: int = Query(
        1, ge=1, le=24, description="URL expiration time in hours"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.VIEWER)),
) -> FileDownloadResponse:
    """
    Generate a temporary download URL for a point cloud file.

    **Required permissions**: Project VIEWER or higher

    **URL expiration**: 1-24 hours (default: 1 hour)
    """
    upload_service = FileUploadService(db)

    # Verify file exists and belongs to project
    pointcloud_file = await upload_service.get_file_by_id(file_id)
    if not pointcloud_file or pointcloud_file.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    if pointcloud_file.status == FileStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="File has been deleted"
        )

    download_url = await upload_service.get_download_url(file_id, expires_in_hours)
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

    return FileDownloadResponse(
        download_url=download_url,
        expires_at=expires_at,
        filename=pointcloud_file.original_filename,
        file_size=pointcloud_file.file_size,
    )


@router.delete(
    "/projects/{project_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete file",
    description="Delete a point cloud file from storage and mark as deleted in database.",
)
async def delete_file(
    project_id: UUID,
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.PROJECT_ADMIN)),
) -> None:
    """
    Delete a point cloud file.

    **Required permissions**: Project ADMIN

    **Note**: This performs a soft delete - the file record remains in the database
    but is marked as deleted and removed from storage.
    """
    upload_service = FileUploadService(db)

    # Verify file exists and belongs to project
    pointcloud_file = await upload_service.get_file_by_id(file_id)
    if not pointcloud_file or pointcloud_file.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    if pointcloud_file.status == FileStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="File already deleted"
        )

    success = await upload_service.delete_file(file_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        )


@router.get(
    "/projects/{project_id}/files/stats",
    response_model=PointCloudStats,
    summary="Get file statistics",
    description="Get statistics about point cloud files in a project.",
)
async def get_project_file_stats(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.VIEWER)),
) -> PointCloudStats:
    """
    Get statistics about point cloud files in a project.

    **Required permissions**: Project VIEWER or higher
    """
    upload_service = FileUploadService(db)

    # Get all files for the project
    all_files = await upload_service.get_project_files(
        project_id=project_id,
        skip=0,
        limit=1000,  # In production, use proper aggregation queries
    )

    total_files = len(all_files)
    total_size = sum(f.file_size for f in all_files)
    total_points = sum(f.point_count for f in all_files if f.point_count)

    # Status breakdown
    uploaded_files = len([f for f in all_files if f.status == FileStatus.UPLOADED])
    processing_files = len([f for f in all_files if f.status == FileStatus.PROCESSING])
    failed_files = len([f for f in all_files if f.status == FileStatus.FAILED])

    # File type breakdown
    file_types = {}
    for f in all_files:
        ext = f.file_extension
        file_types[ext] = file_types.get(ext, 0) + 1

    # Size statistics
    file_sizes_mb = [f.file_size / (1024 * 1024) for f in all_files]
    average_file_size = sum(file_sizes_mb) / len(file_sizes_mb) if file_sizes_mb else 0
    largest_file_size = max(file_sizes_mb) if file_sizes_mb else 0

    return PointCloudStats(
        total_files=total_files,
        total_size=total_size,
        total_points=total_points,
        uploaded_files=uploaded_files,
        processing_files=processing_files,
        failed_files=failed_files,
        file_types=file_types,
        average_file_size=average_file_size,
        largest_file_size=largest_file_size,
    )


# Additional endpoints for advanced file operations


@router.post(
    "/projects/{project_id}/files/{file_id}/reprocess",
    response_model=PointCloudFileResponse,
    summary="Reprocess file",
    description="Trigger reprocessing of a point cloud file to regenerate metadata.",
)
async def reprocess_file(
    project_id: UUID,
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project: Project = Depends(validate_project_exists),
    _: bool = Depends(require_project_access(ProjectRole.PROJECT_ADMIN)),
) -> PointCloudFileResponse:
    """
    Trigger reprocessing of a point cloud file.

    **Required permissions**: Project ADMIN

    This can be useful if:
    - Initial processing failed
    - You want to regenerate metadata with updated algorithms
    - File analysis needs to be refreshed
    """
    upload_service = FileUploadService(db)

    pointcloud_file = await upload_service.get_file_by_id(file_id)
    if not pointcloud_file or pointcloud_file.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    if pointcloud_file.status == FileStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="Cannot reprocess deleted file"
        )

    # TODO: Implement reprocessing logic
    # This would typically involve:
    # 1. Marking file as PROCESSING
    # 2. Queuing a background task for reanalysis
    # 3. Updating metadata when complete

    # For now, return current file state
    return PointCloudFileResponse.model_validate(pointcloud_file)
