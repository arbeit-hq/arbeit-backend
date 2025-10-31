"""
Job Quality Filtering Service

Detects spam/scam jobs and assigns quality scores to filter low-quality postings.
"""
import re
from typing import Tuple
import structlog

from app.models import Job

logger = structlog.get_logger()

# Spam detection patterns
SPAM_KEYWORDS = [
    "telegram", "click here", "earn money", "work from home fast",
    "get rich", "easy money", "no experience needed", "limited time",
    "act now", "make money fast", "guaranteed income", "free training",
    "no interview", "start today", "immediate start", "crypto", "bitcoin",
    "investment opportunity", "passive income", "financial freedom",
    # Generic spam patterns
    "the employment career network",
    "employment career network",
    "career network",
    "welcome! you've reached",
    "you've reached our gateway",
    "gateway to",
    "exciting career possibilities",
    "career possibilities",
    "apply on our portal",
    "visit our portal",
    "register on our",
    "sign up on our platform",
]

SUSPICIOUS_DOMAINS = [
    "telegram.me", "t.me", "bit.ly", "tinyurl.com", "goo.gl",
    "ow.ly", "buff.ly", "adf.ly"
]

# Regex patterns
EXCESSIVE_CAPS_PATTERN = re.compile(r'[A-Z]')
EXCESSIVE_EMOJI_PATTERN = re.compile(r'[\U0001F300-\U0001F9FF]')
EXCESSIVE_EXCLAMATION_PATTERN = re.compile(r'!{2,}')
SUSPICIOUS_EMAIL_PATTERN = re.compile(r'@(gmail|yahoo|hotmail|outlook)\.(com|net|org)', re.IGNORECASE)


def is_spam(job: Job) -> Tuple[bool, str]:
    """
    Detect if a job posting is spam or a scam.
    
    Args:
        job: Job object to check
        
    Returns:
        Tuple of (is_spam: bool, reason: str)
    """
    # Check 1: Missing or empty company name
    if not job.company or len(job.company.strip()) == 0:
        # Allow if it's a well-known job board pattern
        if job.title and len(job.title) > 20:
            pass  # Might be legitimate
        else:
            return (True, "Missing company name")
    
    # Check 2: All-caps title (>80% uppercase)
    if job.title:
        caps_count = len(EXCESSIVE_CAPS_PATTERN.findall(job.title))
        total_letters = len([c for c in job.title if c.isalpha()])
        if total_letters > 0 and (caps_count / total_letters) > 0.8:
            return (True, "Excessive uppercase in title")
    
    # Check 3: Suspicious keywords in title or description
    combined_text = f"{job.title or ''} {job.description or ''}".lower()
    for keyword in SPAM_KEYWORDS:
        if keyword in combined_text:
            return (True, f"Suspicious keyword: {keyword}")
    
    # Check 4: Suspicious URLs
    if job.url:
        for domain in SUSPICIOUS_DOMAINS:
            if domain in job.url.lower():
                return (True, f"Suspicious URL domain: {domain}")
    
    # Check 5: Extremely short description
    if job.description and len(job.description.strip()) < 50:
        return (True, "Description too short (<50 characters)")
    
    # Check 6: Excessive emojis
    if job.description:
        emoji_count = len(EXCESSIVE_EMOJI_PATTERN.findall(job.description))
        if emoji_count > 5:
            return (True, f"Excessive emojis ({emoji_count})")
    
    # Check 7: Multiple exclamation marks
    if job.title and EXCESSIVE_EXCLAMATION_PATTERN.search(job.title):
        return (True, "Multiple exclamation marks in title")
    
    # Check 8: Suspicious email patterns in description
    if job.description and SUSPICIOUS_EMAIL_PATTERN.search(job.description):
        # Only flag if it's in the first 200 characters (likely spam)
        if SUSPICIOUS_EMAIL_PATTERN.search(job.description[:200]):
            return (True, "Suspicious personal email in description")
    
    return (False, "")


def quality_score(job: Job) -> float:
    """
    Calculate quality score for a job posting.
    
    Args:
        job: Job object to score
        
    Returns:
        Float between 0.0 and 1.0
    """
    score = 0.0
    
    # Factor 1: Has company name (0.3)
    if job.company and len(job.company.strip()) > 0:
        score += 0.3
    
    # Factor 2: Has description >100 chars (0.2)
    if job.description and len(job.description.strip()) > 100:
        score += 0.2
    
    # Factor 3: Has location (0.2)
    if job.location and len(job.location.strip()) > 0:
        score += 0.2
    
    # Factor 4: Has salary info (0.2)
    if job.salary_min or job.salary_max:
        score += 0.2
    
    # Factor 5: Proper title formatting (0.1)
    if job.title:
        # Check if title is properly formatted (not all caps, reasonable length)
        caps_count = len(EXCESSIVE_CAPS_PATTERN.findall(job.title))
        total_letters = len([c for c in job.title if c.isalpha()])
        
        if total_letters > 0:
            caps_ratio = caps_count / total_letters
            # Good formatting: 10-100 chars, <50% caps
            if 10 <= len(job.title) <= 100 and caps_ratio < 0.5:
                score += 0.1
    
    return round(score, 2)


def filter_jobs_by_quality(jobs: list[Job], min_score: float = 0.6) -> list[Job]:
    """
    Filter out spam and low-quality jobs.
    
    Args:
        jobs: List of Job objects to filter
        min_score: Minimum quality score threshold (default: 0.6)
        
    Returns:
        List of jobs that pass quality filters
    """
    filtered_jobs = []
    spam_count = 0
    low_quality_count = 0
    
    for job in jobs:
        # Check for spam first
        is_spam_job, spam_reason = is_spam(job)
        if is_spam_job:
            spam_count += 1
            logger.debug(
                "job_filtered_spam",
                job_id=str(job.id),
                title=job.title[:50] if job.title else "N/A",
                reason=spam_reason
            )
            continue
        
        # Check quality score
        score = quality_score(job)
        if score < min_score:
            low_quality_count += 1
            logger.debug(
                "job_filtered_low_quality",
                job_id=str(job.id),
                title=job.title[:50] if job.title else "N/A",
                score=score,
                min_score=min_score
            )
            continue
        
        filtered_jobs.append(job)
    
    logger.info(
        "quality_filtering_complete",
        total_jobs=len(jobs),
        passed=len(filtered_jobs),
        spam_filtered=spam_count,
        low_quality_filtered=low_quality_count
    )
    
    return filtered_jobs


def audit_job_quality(job: Job) -> dict:
    """
    Audit a single job and return quality metrics.
    
    Args:
        job: Job object to audit
        
    Returns:
        Dictionary with audit results
    """
    is_spam_job, spam_reason = is_spam(job)
    score = quality_score(job)
    
    return {
        "job_id": str(job.id),
        "title": job.title,
        "company": job.company,
        "url": job.url,
        "is_spam": is_spam_job,
        "spam_reason": spam_reason,
        "quality_score": score,
        "passed": not is_spam_job and score >= 0.6
    }


# CLI command for auditing existing jobs
if __name__ == "__main__":
    import asyncio
    from sqlalchemy import select
    from app.core.database import SessionLocal
    
    async def audit_all_jobs():
        """Audit all jobs in database and generate report."""
        session = SessionLocal()
        
        try:
            # Get all jobs
            stmt = select(Job).where(Job.is_active)
            result = session.execute(stmt)
            jobs = result.scalars().all()
            
            print("\n{'='*80}")
            print("JOB QUALITY AUDIT REPORT")
            print("{'='*80}\n")
            print("Total jobs to audit: {len(jobs)}\n")
            
            spam_jobs = []
            low_quality_jobs = []
            good_jobs = []
            
            for job in jobs:
                audit_result = audit_job_quality(job)
                
                if audit_result["is_spam"]:
                    spam_jobs.append(audit_result)
                elif audit_result["quality_score"] < 0.6:
                    low_quality_jobs.append(audit_result)
                else:
                    good_jobs.append(audit_result)
            
            # Print summary
            print(f"✅ Good quality jobs: {len(good_jobs)} ({len(good_jobs)/len(jobs)*100:.1f}%)")
            print(f"⚠️  Low quality jobs: {len(low_quality_jobs)} ({len(low_quality_jobs)/len(jobs)*100:.1f}%)")
            print(f"🚫 Spam/scam jobs: {len(spam_jobs)} ({len(spam_jobs)/len(jobs)*100:.1f}%)\n")
            
            # Print spam jobs
            if spam_jobs:
                print(f"\n{'='*80}")
                print(f"SPAM/SCAM JOBS DETECTED ({len(spam_jobs)})")
                print(f"{'='*80}\n")
                for job in spam_jobs[:10]:  # Show first 10
                    print(f"Title: {job['title']}")
                    print(f"Company: {job['company']}")
                    print(f"Reason: {job['spam_reason']}")
                    print(f"URL: {job['url'][:80]}...")
                    print("-" * 80)
                
                if len(spam_jobs) > 10:
                    print(f"\n... and {len(spam_jobs) - 10} more spam jobs\n")
            
            # Print low quality jobs
            if low_quality_jobs:
                print("\n{'='*80}")
                print("LOW QUALITY JOBS ({len(low_quality_jobs)})")
                print("{'='*80}\n")
                for job in low_quality_jobs[:10]:  # Show first 10
                    print(f"Title: {job['title']}")
                    print(f"Company: {job['company']}")
                    print(f"Quality Score: {job['quality_score']}")
                    print(f"URL: {job['url'][:80]}...")
                    print("-" * 80)
                
                if len(low_quality_jobs) > 10:
                    print(f"\n... and {len(low_quality_jobs) - 10} more low quality jobs\n")
            
            print("\n{'='*80}")
            print("AUDIT COMPLETE")
            print("{'='*80}\n")
            
        except Exception as e:
            print(f"Error during audit: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session.close()
    
    asyncio.run(audit_all_jobs())