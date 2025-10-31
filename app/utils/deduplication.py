from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from rapidfuzz import fuzz
import structlog

from app.models import Job
from app.schemas.job import JobIn

logger = structlog.get_logger()


async def is_duplicate(
    session: Session,
    job: JobIn,
    fuzzy_threshold: int = 90,
    days_lookback: int = 90,
    min_length: int = 5  # NEW: Minimum length for fuzzy matching
) -> Tuple[bool, Optional[str]]:
    """
    Check if a job is a duplicate based on URL or fuzzy matching.
    
    Args:
        session: Database session
        job: Job data to check
        fuzzy_threshold: Minimum similarity score (0-100) for fuzzy matching
        days_lookback: Number of days to look back for duplicates
        min_length: Minimum string length for fuzzy matching (avoid false positives)
        
    Returns:
        Tuple of (is_duplicate: bool, existing_job_id: str or None)
    """
    # Check for exact URL match (primary key)
    stmt = select(Job).where(Job.url == job.url)
    result = session.execute(stmt)
    existing_job = result.scalar_one_or_none()
    
    if existing_job:
        logger.info(
            "duplicate_found_url",
            url=job.url,
            existing_job_id=str(existing_job.id)
        )
        return True, str(existing_job.id)
    
    # Check for fuzzy match on title + company in recent jobs
    cutoff_date = datetime.utcnow() - timedelta(days=days_lookback)
    stmt = select(Job).where(
        and_(
            Job.created_at >= cutoff_date,
            Job.is_active
        )
    )
    result = session.execute(stmt)
    recent_jobs = result.scalars().all()
    
    # Fuzzy match on title and company
    for existing_job in recent_jobs:
        # Skip if strings are too short (avoid false positives)
        if (not existing_job.company or not job.company or 
            len(existing_job.company) < min_length or len(job.company) < min_length):
            continue
        
        if len(existing_job.title) < min_length or len(job.title) < min_length:
            continue
            
        # Calculate similarity scores
        title_similarity = fuzz.ratio(
            job.title.lower(),
            existing_job.title.lower()
        )
        company_similarity = fuzz.ratio(
            job.company.lower(),
            existing_job.company.lower()
        )
        
        # Combined score (weighted average)
        combined_score = (title_similarity * 0.7) + (company_similarity * 0.3)
        
        if combined_score >= fuzzy_threshold:
            logger.info(
                "duplicate_found_fuzzy",
                job_title=job.title,
                existing_title=existing_job.title,
                similarity_score=combined_score,
                existing_job_id=str(existing_job.id)
            )
            return True, str(existing_job.id)
    
    return False, None


async def merge_duplicate_metadata(
    session: Session,
    existing_job_id: str,
    new_job_data: JobIn
) -> None:
    """
    Update existing job with new data if it has more information.
    
    Args:
        session: Database session
        existing_job_id: ID of existing job
        new_job_data: New job data to potentially merge
    """
    stmt = select(Job).where(Job.id == existing_job_id)
    result = session.execute(stmt)
    existing_job = result.scalar_one_or_none()
    
    if not existing_job:
        logger.warning("merge_job_not_found", job_id=existing_job_id)
        return
    
    updated = False
    
    # Update description if new one is longer
    if new_job_data.description and (
        not existing_job.description or 
        len(new_job_data.description) > len(existing_job.description)
    ):
        existing_job.description = new_job_data.description
        updated = True
    
    # Update salary if not present
    if new_job_data.salary_min and not existing_job.salary_min:
        existing_job.salary_min = new_job_data.salary_min
        updated = True
    
    if new_job_data.salary_max and not existing_job.salary_max:
        existing_job.salary_max = new_job_data.salary_max
        updated = True
    
    # Update location if not present
    if new_job_data.location and not existing_job.location:
        existing_job.location = new_job_data.location
        updated = True
    
    # Update remote_work flag
    if new_job_data.remote_work and not existing_job.remote_work:
        existing_job.remote_work = new_job_data.remote_work
        updated = True
    
    if updated:
        existing_job.updated_at = datetime.utcnow()
        session.commit()
        logger.info(
            "job_metadata_merged",
            job_id=existing_job_id,
            title=existing_job.title
        )


def cross_source_dedup(jobs: list[JobIn]) -> list[JobIn]:
    """
    Remove duplicates within a batch before DB insertion.
    
    Args:
        jobs: List of jobs to deduplicate
        
    Returns:
        Deduplicated list of jobs
    """
    seen_urls = set()
    seen_titles = {}
    unique_jobs = []
    
    for job in jobs:
        # Check URL duplicates
        if job.url in seen_urls:
            logger.debug("batch_duplicate_url", url=job.url)
            continue
        
        # Check fuzzy title duplicates
        is_fuzzy_dup = False
        job_key = f"{job.title.lower()}_{job.company.lower() if job.company else ''}"
        
        for seen_key in seen_titles.keys():
            similarity = fuzz.ratio(job_key, seen_key)
            if similarity >= 90:
                logger.debug(
                    "batch_duplicate_fuzzy",
                    title=job.title,
                    similarity=similarity
                )
                is_fuzzy_dup = True
                break
        
        if not is_fuzzy_dup:
            seen_urls.add(job.url)
            seen_titles[job_key] = job
            unique_jobs.append(job)
    
    logger.info(
        "batch_deduplication_complete",
        original_count=len(jobs),
        unique_count=len(unique_jobs),
        duplicates_removed=len(jobs) - len(unique_jobs)
    )
    
    return unique_jobs