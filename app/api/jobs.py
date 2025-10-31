"""
Jobs API endpoints
"""
from datetime import datetime, timedelta
from typing import List, Optional
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_, desc, func
import structlog
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User, Job, UserPreference
from app.schemas.job import JobOut, JobMatchOut
from app.utils.matching import match_job

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = structlog.get_logger()


@router.get("/search", response_model=List[JobOut])
async def search_jobs(
    response: Response,
    keywords: Optional[str] = Query(None, description="Keywords to search (comma-separated)"),
    location: Optional[str] = Query(None, description="Location filter"),
    remote: Optional[bool] = Query(None, description="Remote jobs only"),
    min_salary: Optional[int] = Query(None, ge=0, description="Minimum salary"),
    max_salary: Optional[int] = Query(None, ge=0, description="Maximum salary"),
    job_type: Optional[str] = Query(None, description="Job type filter"),
    min_quality: float = Query(0.6, ge=0.0, le=1.0, description="Minimum quality score"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """
    Search jobs with filters.
    
    Public endpoint - no authentication required.
    """
    # Build query
    query = select(Job).where(Job.is_active)

    # Apply quality filter - exclude jobs without quality scores
    if min_quality > 0:
        query = query.where(
            and_(
                Job.quality_score.is_not(None),
                Job.quality_score >= min_quality
            )
        )
    else:
        # Even with min_quality=0, exclude spam (quality_score < 0.3)
        query = query.where(
            or_(
                Job.quality_score >= 0.3,
                Job.quality_score.is_(None)
            )
        )

    # Keyword search
    if keywords:
        keyword_list = [k.strip() for k in keywords.split(',')]
        keyword_filters = []
        for keyword in keyword_list:
            keyword_filters.append(
                or_(
                    Job.title.ilike(f'%{keyword}%'),
                    Job.description.ilike(f'%{keyword}%'),
                    Job.company.ilike(f'%{keyword}%')
                )
            )
        if keyword_filters:
            query = query.where(or_(*keyword_filters))

    # Location filter
    if location:
        query = query.where(
            or_(
                Job.location.ilike(f'%{location}%'),
                Job.remote_work  # Include remote jobs
            )
        )

    # Remote filter
    if remote is True:
        query = query.where(Job.remote_work)

    # Salary filters
    if min_salary is not None:
        query = query.where(
        or_(
            Job.salary_max >= min_salary,
            Job.salary_min >= min_salary,
            and_(Job.salary_min.is_(None), Job.salary_max.is_(None))  # Include jobs without salary
        )
    )

    if max_salary is not None:
        query = query.where(
        or_(
            Job.salary_min <= max_salary,
            Job.salary_max <= max_salary,
            and_(Job.salary_min.is_(None), Job.salary_max.is_(None))  # Include jobs without salary
        )
    )

    # Job type filter
    if job_type:
        query = query.where(Job.job_type.ilike(f'%{job_type}%'))

    # Order by quality score and recency
    query = query.order_by(
        desc(Job.quality_score),
        desc(Job.posted_at),
        desc(Job.created_at)
    )

    # Get total count before pagination
    count_stmt = select(func.count(Job.id)).select_from(query.subquery())
    total_count = db.execute(count_stmt).scalar()

    # Apply pagination
    query = query.offset(offset).limit(limit)

    # Execute query
    result = db.execute(query)
    jobs = result.scalars().all()

    # Set total count header for frontend pagination
    response.headers["X-Total-Count"] = str(total_count)

    logger.info(
        "jobs_searched",
        keywords=keywords,
        location=location,
        remote=remote,
        total_count=total_count,
        results_count=len(jobs)
    )

    return jobs


@router.get("/matched", response_model=List[JobMatchOut])
async def get_matched_jobs(
    min_score: float = Query(0.3, ge=0.0, le=1.0, description="Minimum relevance score"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get jobs matched to current user's preferences.

    Requires authentication and user preferences to be set.
    """
    # Get user preferences
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = db.execute(stmt)
    preferences = result.scalar_one_or_none()

    if not preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User preferences not set. Please create preferences first at /preferences"
        )

    # Get recent active jobs (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    query = select(Job).where(
        and_(
            Job.is_active,
            Job.created_at >= thirty_days_ago
        )
    )

    # Apply quality filter
    query = query.where(
        or_(
            Job.quality_score >= 0.6,
            Job.quality_score.is_(None)
        )
    )

    # Order by recency
    query = query.order_by(desc(Job.created_at))

    result = db.execute(query)
    all_jobs = result.scalars().all()

    # Calculate match scores for each job
    matched_jobs = []
    for job in all_jobs:
        relevance_score, match_reasons = match_job(job, preferences)

        if relevance_score >= min_score:
            # Create response object with match data
            job_dict = {
                "id": job.id,
                "title": job.title,
                "url": job.url,
                "company": job.company,
                "location": job.location,
                "description": job.description,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "remote_work": job.remote_work,
                "job_type": job.job_type,
                "quality_score": job.quality_score,
                "source_id": job.source_id,
                "posted_at": job.posted_at,
                "is_active": job.is_active,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "relevance_score": relevance_score,
                "match_reasons": match_reasons
            }
            matched_jobs.append(job_dict)

    # Sort by relevance score
    matched_jobs.sort(key=lambda x: x["relevance_score"], reverse=True)

    # Apply pagination
    paginated_jobs = matched_jobs[offset:offset + limit]

    logger.info(
        "jobs_matched",
        user_id=str(current_user.id),
        total_jobs_checked=len(all_jobs),
        matched_count=len(matched_jobs),
        returned_count=len(paginated_jobs),
        min_score=min_score
    )

    return paginated_jobs


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific job by ID.

    Public endpoint - no authentication required.
    """
    try:
        job_uuid = uuid_lib.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job ID format"
        ) from exc

    stmt = select(Job).where(Job.id == job_uuid)
    result = db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    logger.info("job_retrieved", job_id=job_id)
    return job