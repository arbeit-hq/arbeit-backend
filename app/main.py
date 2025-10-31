from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.api import router as api_router
from app.api import admin, preferences, jobs
from app.logging_config import LoggingMiddleware
import structlog

logger = structlog.get_logger()

def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Arbeit - Intelligent Job Monitoring Platform",
        description="RSS Reader for Jobs - Monitor job opportunities across all sources",
        version="0.1.0",
        debug=settings.debug
    )

    # Rate limiting setup
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add logging middleware
    app.add_middleware(LoggingMiddleware)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router, prefix="/api")
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(preferences.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")

    # Startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        """Start background services on app startup."""
        try:
            from app.scheduler.digest import start_digest_scheduler
            start_digest_scheduler()
            logger.info("app_startup_complete", services=["digest_scheduler"])
        except Exception as e:
            logger.error("app_startup_failed", error=str(e))

    @app.on_event("shutdown")
    async def shutdown_event():
        """Stop background services on app shutdown."""
        try:
            from app.scheduler.digest import stop_digest_scheduler
            stop_digest_scheduler()
            logger.info("app_shutdown_complete")
        except Exception as e:
            logger.error("app_shutdown_failed", error=str(e))

    # Health check endpoint (no rate limiting)
    @app.get("/health")
    async def health_check():
        """Health check endpoint for load balancers and monitoring."""
        return JSONResponse(
            content={"status": "ok"},
            status_code=200
        )

    # Test endpoint to demonstrate rate limiting
    @app.get("/test")
    @limiter.limit("100/minute")
    @limiter.limit("1000/hour")
    async def test_rate_limit(request: Request):
        """Test endpoint that demonstrates rate limiting."""
        return JSONResponse(
            content={"message": "Request successful", "ip": request.client.host},
            status_code=200
        )

    return app

# Create the FastAPI app
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
