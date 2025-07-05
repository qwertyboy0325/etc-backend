"""API v1 router configuration."""

from fastapi import APIRouter

# Import route modules
from app.api.v1.health import router as health_router

# from app.api.v1.routes import auth, users, projects, tasks, annotations

# Create main API router
api_router = APIRouter()

# Include health check routes
api_router.include_router(health_router, prefix="/system", tags=["System"])

# Include all route modules (commented out for now)
# api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
# api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
# api_router.include_router(annotations.router, prefix="/annotations", tags=["Annotations"])


# Root endpoint for API v1
@api_router.get("/", tags=["Root"])
async def api_root():
    """API v1 root endpoint."""
    return {
        "message": "ETC Point Cloud Annotation System API v1",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "health": "/system/health",
            "database_status": "/system/database/status",
            "models_validate": "/system/models/validate",
            "system_info": "/system/info",
            "ping": "/system/ping",
        },
    }


# Temporary test route
@api_router.get("/test", tags=["Test"])
async def test_endpoint():
    """Test endpoint to verify API is working."""
    return {"message": "API is working!", "version": "1.0.0"}
