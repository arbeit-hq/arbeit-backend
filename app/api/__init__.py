from fastapi import APIRouter

from app.api import auth

# Create the main API router
router = APIRouter()

# Include auth routes
router.include_router(auth.router, prefix="/auth", tags=["authentication"])

@router.get("/")
async def api_root():
    """API root endpoint."""
    return {"message": "Arbeit API - Intelligent Job Monitoring Platform"}