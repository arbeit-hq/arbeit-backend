"""
Job Matching Engine

Matches jobs to user preferences based on keywords, location, salary, and quality.
"""
from typing import Dict
from datetime import datetime
from rapidfuzz import fuzz
import structlog

from app.models import Job, UserPreference

logger = structlog.get_logger()


def score_keywords(job: Job, prefs: UserPreference) -> float:
    """
    Score job based on keyword matching.
    
    Args:
        job: Job to score
        prefs: User preferences
        
    Returns:
        Float score between 0.0 and 1.0
    """
    if not prefs.keywords or len(prefs.keywords) == 0:
        return 1.0  # No keyword filter, all jobs match
    
    # Check excluded keywords first
    if prefs.excluded_keywords:
        combined_text = f"{job.title or ''} {job.description or ''}".lower()
        for excluded in prefs.excluded_keywords:
            if excluded.lower() in combined_text:
                logger.debug(
                    "job_excluded_by_keyword",
                    job_id=str(job.id),
                    excluded_keyword=excluded
                )
                return 0.0
    
    # Count keyword matches
    title_text = (job.title or '').lower()
    desc_text = (job.description or '').lower()
    
    title_matches = 0
    desc_matches = 0
    
    for keyword in prefs.keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in title_text:
            title_matches += 1
        if keyword_lower in desc_text:
            desc_matches += 1
    
    # Calculate weighted score
    # Title matches weight: 2.0, Description matches weight: 1.0
    total_keywords = len(prefs.keywords)
    max_possible_score = total_keywords * 3  # Each keyword can match in both title (2) and desc (1)
    
    actual_score = (title_matches * 2) + desc_matches
    score = actual_score / max_possible_score if max_possible_score > 0 else 0.0
    
    return round(min(score, 1.0), 3)


def filter_location(job: Job, prefs: UserPreference) -> bool:
    """
    Filter job based on location preference.
    
    Args:
        job: Job to filter
        prefs: User preferences
        
    Returns:
        True if job passes location filter, False otherwise
    """
    # No location preference
    if not prefs.location and not prefs.remote_only:
        return True
    
    # Remote only filter
    if prefs.remote_only:
        if job.remote_work:
            return True
        if job.location and 'remote' in job.location.lower():
            return True
        logger.debug(
            "job_filtered_not_remote",
            job_id=str(job.id),
            location=job.location
        )
        return False
    
    # Location matching
    if prefs.location:
        job_location = (job.location or '').lower()
        pref_location = prefs.location.lower()
        
        # Exact substring match
        if pref_location in job_location:
            return True
        
        # Fuzzy match with threshold > 85%
        similarity = fuzz.ratio(pref_location, job_location)
        if similarity > 85:
            return True
        
        # Check if preference is part of job location (e.g., "Berlin" in "Berlin, Germany")
        if ',' in job_location:
            location_parts = [part.strip() for part in job_location.split(',')]
            for part in location_parts:
                if pref_location in part or fuzz.ratio(pref_location, part) > 85:
                    return True
        
        logger.debug(
            "job_filtered_location_mismatch",
            job_id=str(job.id),
            job_location=job.location,
            pref_location=prefs.location,
            similarity=similarity
        )
        return False
    
    return True


def filter_salary(job: Job, prefs: UserPreference) -> bool:
    """
    Filter job based on salary preference.
    
    Args:
        job: Job to filter
        prefs: User preferences
        
    Returns:
        True if job passes salary filter, False otherwise
    """
    # No salary filter
    if prefs.salary_min is None and prefs.salary_max is None:
        return True
    
    # Job has no salary data - don't filter out (but will affect match score)
    if job.salary_min is None and job.salary_max is None:
        return True
    
    # Check salary_min preference
    if prefs.salary_min is not None:
        # Job's max salary must be >= user's min requirement
        if job.salary_max is not None and job.salary_max < prefs.salary_min:
            logger.debug(
                "job_filtered_salary_too_low",
                job_id=str(job.id),
                job_salary_max=job.salary_max,
                pref_salary_min=prefs.salary_min
            )
            return False
        
        # If only job.salary_min exists, check that
        if job.salary_max is None and job.salary_min is not None:
            if job.salary_min < prefs.salary_min:
                return False
    
    # Check salary_max preference
    if prefs.salary_max is not None:
        # Job's min salary must be <= user's max budget
        if job.salary_min is not None and job.salary_min > prefs.salary_max:
            logger.debug(
                "job_filtered_salary_too_high",
                job_id=str(job.id),
                job_salary_min=job.salary_min,
                pref_salary_max=prefs.salary_max
            )
            return False
    
    return True


def filter_job_type(job: Job, prefs: UserPreference) -> bool:
    """
    Filter job based on job type preference.
    
    Args:
        job: Job to filter
        prefs: User preferences
        
    Returns:
        True if job passes job type filter, False otherwise
    """
    # No job type filter
    if not prefs.job_types or len(prefs.job_types) == 0:
        return True
    
    # Job has no type specified - allow it
    if not job.job_type:
        return True
    
    # Check if job type matches any preferred types
    job_type_lower = job.job_type.lower()
    for pref_type in prefs.job_types:
        if pref_type.lower() in job_type_lower:
            return True
    
    logger.debug(
        "job_filtered_job_type_mismatch",
        job_id=str(job.id),
        job_type=job.job_type,
        pref_types=prefs.job_types
    )
    return False


def match_job(job: Job, prefs: UserPreference) -> tuple[float, Dict[str, any]]:
    """
    Calculate relevance score for a job based on user preferences.
    
    Args:
        job: Job to match
        prefs: User preferences
        
    Returns:
        Tuple of (relevance_score: float, match_reasons: dict)
    """
    match_reasons = {
        "keyword_score": 0.0,
        "has_salary": False,
        "is_remote": False,
        "is_recent": False,
        "high_quality": False,
        "matched_keywords": [],
        "filters_passed": []
    }
    
    # Step 1: Check quality score
    if job.quality_score is not None and job.quality_score < 0.6:
        logger.debug(
            "job_filtered_low_quality",
            job_id=str(job.id),
            quality_score=job.quality_score
        )
        return (0.0, match_reasons)
    
    # Step 2: Apply filters
    if not filter_location(job, prefs):
        return (0.0, match_reasons)
    match_reasons["filters_passed"].append("location")
    
    if not filter_salary(job, prefs):
        return (0.0, match_reasons)
    match_reasons["filters_passed"].append("salary")
    
    if not filter_job_type(job, prefs):
        return (0.0, match_reasons)
    match_reasons["filters_passed"].append("job_type")
    
    # Step 3: Calculate base score from keywords
    base_score = score_keywords(job, prefs)
    match_reasons["keyword_score"] = base_score
    
    # Track which keywords matched
    if prefs.keywords:
        combined_text = f"{job.title or ''} {job.description or ''}".lower()
        for keyword in prefs.keywords:
            if keyword.lower() in combined_text:
                match_reasons["matched_keywords"].append(keyword)
    
    # Step 4: Apply bonuses
    bonus = 0.0
    
    # Has salary info: +0.1
    if job.salary_min or job.salary_max:
        bonus += 0.1
        match_reasons["has_salary"] = True
    
    # Remote job (if remote_only=True): +0.15
    if prefs.remote_only and job.remote_work:
        bonus += 0.15
        match_reasons["is_remote"] = True
    
    # Posted within last 7 days: +0.1
    if job.posted_at:
        days_old = (datetime.utcnow() - job.posted_at).days
        if days_old <= 7:
            bonus += 0.1
            match_reasons["is_recent"] = True
    
    # High quality score (>0.8): +0.1
    if job.quality_score and job.quality_score > 0.8:
        bonus += 0.1
        match_reasons["high_quality"] = True
    
    # Step 5: Calculate final score
    final_score = base_score + bonus
    final_score = min(final_score, 1.0)  # Cap at 1.0
    final_score = round(final_score, 3)
    
    logger.debug(
        "job_matched",
        job_id=str(job.id),
        base_score=base_score,
        bonus=bonus,
        final_score=final_score
    )
    
    return (final_score, match_reasons)