from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
import structlog
import uuid

from app.models import ScraperLog, JobSource, LogLevelEnum

logger = structlog.get_logger()


def log_scraper_event(
    session: Session,
    source_id: uuid.UUID,
    level: LogLevelEnum,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a scraper event to the database.
    
    Args:
        session: Database session
        source_id: ID of the job source
        level: Log level (info, warning, error)
        message: Log message
        metadata: Additional metadata as JSON
    """
    log_entry = ScraperLog(
        source_id=source_id,
        level=level,
        message=message,
        extra_data=metadata or {},  # FIX: Changed from metadata to extra_data
        created_at=datetime.utcnow()
    )
    session.add(log_entry)
    session.commit()
    
    # Also log to structlog
    log_func = getattr(logger, level.value)
    log_func(
        "scraper_event",
        source_id=str(source_id),
        message=message,
        extra_data=metadata  # FIX: Changed from metadata to extra_data
    )


def get_source_health_report(
    session: Session,
    source_id: uuid.UUID,
    days: int = 7
) -> Dict[str, Any]:
    """
    Get health report for a job source.
    
    Args:
        session: Database session
        source_id: ID of the job source
        days: Number of days to analyze
        
    Returns:
        Dictionary with health metrics
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get source info
    stmt = select(JobSource).where(JobSource.id == source_id)
    result = session.execute(stmt)
    source = result.scalar_one_or_none()
    
    if not source:
        return {"error": "Source not found"}
    
    # Count logs by level
    stmt = select(
        ScraperLog.level,
        func.count(ScraperLog.id).label('count')
    ).where(
        and_(
            ScraperLog.source_id == source_id,
            ScraperLog.created_at >= cutoff_date
        )
    ).group_by(ScraperLog.level)
    
    result = session.execute(stmt)
    log_counts = {row.level.value: row.count for row in result}
    
    # Calculate success rate
    total_logs = sum(log_counts.values())
    error_count = log_counts.get('error', 0)
    success_rate = ((total_logs - error_count) / total_logs * 100) if total_logs > 0 else 0
    
    # Get recent errors
    stmt = select(ScraperLog).where(
        and_(
            ScraperLog.source_id == source_id,
            ScraperLog.level == LogLevelEnum.ERROR,
            ScraperLog.created_at >= cutoff_date
        )
    ).order_by(ScraperLog.created_at.desc()).limit(5)
    
    result = session.execute(stmt)
    recent_errors = [
        {
            "message": log.message,
            "created_at": log.created_at.isoformat(),
            "extra_data": log.extra_data  # FIX: Changed from metadata to extra_data
        }
        for log in result.scalars().all()
    ]
    
    return {
        "source_name": source.name,
        "source_id": str(source_id),
        "period_days": days,
        "total_jobs_found": source.total_jobs_found,
        "total_errors": source.total_errors,
        "success_rate": round(success_rate, 2),
        "log_counts": log_counts,
        "recent_errors": recent_errors,
        "last_scraped_at": source.last_scraped_at.isoformat() if source.last_scraped_at else None,
        "is_active": source.is_active
    }


def detect_source_degradation(
    session: Session,
    source_id: uuid.UUID,
    threshold: float = 0.5
) -> bool:
    """
    Detect if a source is degrading (increasing failure rate).
    
    Args:
        session: Database session
        source_id: ID of the job source
        threshold: Failure rate threshold (0.0-1.0)
        
    Returns:
        True if source is degrading, False otherwise
    """
    # Check last 24 hours
    cutoff_date = datetime.utcnow() - timedelta(hours=24)
    
    # Count total logs and error logs separately
    stmt_total = select(func.count(ScraperLog.id)).where(
        and_(
            ScraperLog.source_id == source_id,
            ScraperLog.created_at >= cutoff_date
        )
    )
    
    stmt_errors = select(func.count(ScraperLog.id)).where(
        and_(
            ScraperLog.source_id == source_id,
            ScraperLog.level == LogLevelEnum.ERROR,
            ScraperLog.created_at >= cutoff_date
        )
    )
    
    total = session.execute(stmt_total).scalar() or 0
    errors = session.execute(stmt_errors).scalar() or 0
    
    if total == 0:
        return False
    
    error_rate = errors / total
    
    if error_rate >= threshold:
        logger.warning(
            "source_degradation_detected",
            source_id=str(source_id),
            error_rate=error_rate,
            threshold=threshold
        )
        return True
    
    return False