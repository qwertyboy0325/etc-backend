"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router

# Import route modules
from app.api.v1.health import router as health_router
from app.api.v1.pointcloud import router as pointcloud_router
from app.api.v1.projects import router as projects_router

# Create main API router
api_router = APIRouter()

# Include health check routes
api_router.include_router(health_router, prefix="/system", tags=["System"])

# Include authentication routes
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Include project management routes
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])

# Include point cloud file management routes
api_router.include_router(pointcloud_router, tags=["Point Cloud Files"])

# Include other route modules (to be implemented)
# from app.api.v1.users import router as users_router
# from app.api.v1.tasks import router as tasks_router
# from app.api.v1.annotations import router as annotations_router

# api_router.include_router(users_router, prefix="/users", tags=["Users"])
# api_router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
# api_router.include_router(annotations_router, prefix="/annotations", tags=["Annotations"])


# Root endpoint for API v1
@api_router.get("/", tags=["Root"])
async def api_root():
    """API v1 root endpoint."""
    return {
        "message": "ETC Point Cloud Annotation System API v1",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            # System endpoints
            "health": "/system/health",
            "database_status": "/system/database/status",
            "models_validate": "/system/models/validate",
            "system_info": "/system/info",
            "ping": "/system/ping",
            # Authentication endpoints
            "register": "/auth/register",
            "login": "/auth/login",
            "logout": "/auth/logout",
            "refresh": "/auth/refresh",
            "me": "/auth/me",
            "verify_token": "/auth/verify-token",
            "change_password": "/auth/change-password",
            "deactivate": "/auth/deactivate",
            # Project endpoints
            "projects": "/projects",
            "create_project": "/projects",
            "project_members": "/projects/{project_id}/members",
            # Point cloud file endpoints
            "upload_file": "/projects/{project_id}/files/upload",
            "list_files": "/projects/{project_id}/files",
            "file_details": "/projects/{project_id}/files/{file_id}",
            "download_file": "/projects/{project_id}/files/{file_id}/download",
            "file_stats": "/projects/{project_id}/files/stats",
        },
    }


# Temporary test route
@api_router.get("/test", tags=["Test"])
async def test_endpoint():
    """Test endpoint to verify API is working."""
    return {"message": "API is working!", "version": "1.0.0"}
