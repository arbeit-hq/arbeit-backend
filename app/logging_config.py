import time
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware



def configure_structlog():
    """Configure structlog for structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests with structured data."""

    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()
        
        # Get logger
        logger = structlog.get_logger("arbeit.api")
        
        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            processing_time = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(processing_time, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
        
        # Calculate duration
        processing_time = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(processing_time, 2),
        )
        
        return response


# Initialize structlog configuration
configure_structlog()