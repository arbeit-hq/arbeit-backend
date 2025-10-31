"""
Daily digest scheduler using APScheduler.
Sends personalized job digests to users based on their notification preferences.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import structlog

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    BackgroundScheduler = None
    CronTrigger = None
    SCHEDULER_AVAILABLE = False

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import User, UserPreference, Job
from app.services.email_service import EmailService
from app.utils.matching import match_job

logger = structlog.get_logger()

# Initialize scheduler
if SCHEDULER_AVAILABLE:
    scheduler = BackgroundScheduler()
else:
    scheduler = None
    logger.warning("apscheduler_not_installed", message="APScheduler not available. Install with: pip install apscheduler")


def get_matched_jobs_for_user(user: User, db: Session, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top matched jobs for a user based on their preferences.
    
    Args:
        user: User object
        db: Database session
        limit: Maximum number of jobs to return
    
    Returns:
        List of matched jobs with relevance scores
    """
    # Get user preferences
    stmt = select(UserPreference).where(UserPreference.user_id == user.id)
    result = db.execute(stmt)
    preference = result.scalar_one_or_none()
    
    if not preference or not preference.keywords:
        logger.warning("no_preferences_for_digest", user_id=str(user.id))
        return []
    
    # Get recent jobs (last 24 hours for daily, last 7 days for weekly)
    time_threshold = datetime.utcnow() - timedelta(days=1)
    
    # Query jobs
    stmt = select(Job).where(
        and_(
            Job.is_active,
            Job.created_at >= time_threshold,
            Job.quality_score >= 0.6  # Only high-quality jobs
        )
    ).order_by(Job.created_at.desc()).limit(100)  # Get recent jobs
    
    result = db.execute(stmt)
    jobs = result.scalars().all()
    
    if not jobs:
        logger.info("no_recent_jobs_for_digest", user_id=str(user.id))
        return []
    
    # Match and score jobs
    matched_jobs = []
    for job in jobs:
        score, reasons = match_job(job, preference)
        
        if score >= 0.3:  # Minimum relevance threshold
            matched_jobs.append({
                "title": job.title,
                "company": job.company or "Unknown Company",
                "location": job.location,
                "url": job.url,
                "score": score,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "remote": job.remote_work,
                "reasons": reasons
            })
    
    # Sort by relevance score and return top N
    matched_jobs.sort(key=lambda x: x["score"], reverse=True)
    return matched_jobs[:limit]


def send_daily_digests():
    """
    Send daily digest emails to all users with daily notification frequency.
    Runs at 08:00 UTC every day.
    """
    logger.info("daily_digest_job_started")
    
    db = SessionLocal()
    try:
        # Get all users with daily notification frequency
        stmt = select(User).join(UserPreference).where(
            and_(
                UserPreference.notification_frequency == "daily",
                User.is_verified
            )
        )
        result = db.execute(stmt)
        users = result.scalars().all()
        
        logger.info("daily_digest_users_found", count=len(users))
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # Get matched jobs for user
                matched_jobs = get_matched_jobs_for_user(user, db, limit=10)
                
                if not matched_jobs:
                    logger.info("no_matches_for_user", user_id=str(user.id), user_email=user.email)
                    continue
                
                # Send digest email
                success = EmailService.send_digest(user, matched_jobs)
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(
                    "digest_send_failed_for_user",
                    user_id=str(user.id),
                    user_email=user.email,
                    error=str(e)
                )
                failed_count += 1
        
        logger.info(
            "daily_digest_job_completed",
            total_users=len(users),
            sent=sent_count,
            failed=failed_count
        )
        
    except Exception as e:
        logger.error("daily_digest_job_failed", error=str(e))
    finally:
        db.close()


def send_weekly_digests():
    """
    Send weekly digest emails to all users with weekly notification frequency.
    Runs at 08:00 UTC every Monday.
    """
    logger.info("weekly_digest_job_started")
    
    db = SessionLocal()
    try:
        # Get all users with weekly notification frequency
        stmt = select(User).join(UserPreference).where(
            and_(
                UserPreference.notification_frequency == "weekly",
                User.is_verified
            )
        )
        result = db.execute(stmt)
        users = result.scalars().all()
        
        logger.info("weekly_digest_users_found", count=len(users))
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # Get matched jobs for user (last 7 days)
                stmt_pref = select(UserPreference).where(UserPreference.user_id == user.id)
                result_pref = db.execute(stmt_pref)
                preference = result_pref.scalar_one_or_none()
                
                if not preference or not preference.keywords:
                    continue
                
                # Get jobs from last 7 days
                time_threshold = datetime.utcnow() - timedelta(days=7)
                
                stmt_jobs = select(Job).where(
                    and_(
                        Job.is_active,
                        Job.created_at >= time_threshold,
                        Job.quality_score >= 0.6
                    )
                ).order_by(Job.created_at.desc()).limit(200)
                
                result_jobs = db.execute(stmt_jobs)
                jobs = result_jobs.scalars().all()
                
                # Match and score jobs
                matched_jobs = []
                for job in jobs:
                    score, reasons = match_job(job, preference)
                    
                    if score >= 0.3:
                        matched_jobs.append({
                            "title": job.title,
                            "company": job.company or "Unknown Company",
                            "location": job.location,
                            "url": job.url,
                            "score": score,
                            "salary_min": job.salary_min,
                            "salary_max": job.salary_max,
                            "remote": job.remote_work,
                            "reasons": reasons
                        })
                
                matched_jobs.sort(key=lambda x: x["score"], reverse=True)
                top_matches = matched_jobs[:15]  # More jobs for weekly digest
                
                if not top_matches:
                    logger.info("no_matches_for_user", user_id=str(user.id), user_email=user.email)
                    continue
                
                # Send digest email
                success = EmailService.send_digest(user, top_matches)
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(
                    "digest_send_failed_for_user",
                    user_id=str(user.id),
                    user_email=user.email,
                    error=str(e)
                )
                failed_count += 1
        
        logger.info(
            "weekly_digest_job_completed",
            total_users=len(users),
            sent=sent_count,
            failed=failed_count
        )
        
    except Exception as e:
        logger.error("weekly_digest_job_failed", error=str(e))
    finally:
        db.close()


def start_digest_scheduler():
    """
    Start the digest scheduler with daily and weekly jobs.
    """
    # Daily digest at 08:00 UTC
    scheduler.add_job(
        send_daily_digests,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_digest",
        name="Send daily job digests",
        replace_existing=True
    )
    
    # Weekly digest on Monday at 08:00 UTC
    scheduler.add_job(
        send_weekly_digests,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_digest",
        name="Send weekly job digests",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("digest_scheduler_started", jobs=["daily_digest", "weekly_digest"])


def stop_digest_scheduler():
    """Stop the digest scheduler."""
    scheduler.shutdown()
    logger.info("digest_scheduler_stopped")


# For manual testing
if __name__ == "__main__":
    logger.info("running_digest_manually")
    send_daily_digests()