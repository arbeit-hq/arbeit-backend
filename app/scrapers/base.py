import asyncio
import random
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
import httpx
import structlog
from sqlalchemy.orm import Session

from app.models import JobSource, Job
from app.schemas.job import JobIn
from app.utils.deduplication import is_duplicate, merge_duplicate_metadata
from app.utils.logging import log_scraper_event
from app.models import LogLevelEnum

logger = structlog.get_logger()


class BaseScraper(ABC):
    """Base class for all job scrapers"""
    
    # User agent rotation pool
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    ]
    
    def __init__(
        self,
        source_name: str,
        session: Session,
        timeout: int = 10,
        max_retries: int = 3,
        rate_limit_delay: float = 1.0
    ):
        """
        Initialize base scraper.
        
        Args:
            source_name: Name of the job source
            session: Database session
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            rate_limit_delay: Delay between requests in seconds
        """
        self.source_name = source_name
        self.session = session
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self.source: Optional[JobSource] = None
        
    def _get_random_user_agent(self) -> str:
        """Get a random user agent from the pool"""
        return random.choice(self.USER_AGENTS)
        
    async def fetch(self, url: str) -> Optional[bytes]:
        """
        Fetch content from URL with retry logic and user-agent rotation.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response content as bytes, or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'User-Agent': self._get_random_user_agent(),
                    'Accept': 'application/json, text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers, follow_redirects=True)
                    response.raise_for_status()
                    
                    # Rate limiting
                    if self.rate_limit_delay > 0:
                        await asyncio.sleep(self.rate_limit_delay)
                    
                    logger.info(
                        "fetch_success",
                        url=url,
                        status_code=response.status_code,
                        attempt=attempt + 1
                    )
                    return response.content
                    
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "fetch_http_error",
                    url=url,
                    status_code=e.response.status_code,
                    attempt=attempt + 1
                )
                if e.response.status_code == 429:  # Rate limited
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                elif e.response.status_code >= 500:  # Server error, retry
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:  # Client error, don't retry
                    break
                    
            except httpx.RequestError as e:
                logger.warning(
                    "fetch_request_error",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1
                )
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(
                    "fetch_unexpected_error",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1
                )
                
        return None
    
    @abstractmethod
    async def parse(self, content: bytes) -> List[JobIn]:
        """
        Parse content and extract job listings.
        
        Args:
            content: Raw content from fetch()
            
        Returns:
            List of JobIn objects
        """
        pass
    
    async def save(self, jobs: List[JobIn]) -> int:
        """
        Save jobs to database with duplicate checking and bulk insert.
        
        Args:
            jobs: List of jobs to save
            
        Returns:
            Number of jobs successfully saved
        """
        if not self.source:
            logger.error("save_no_source", source_name=self.source_name)
            return 0
        
        saved_count = 0
        duplicate_count = 0
        error_count = 0
        jobs_to_insert = []

        from app.utils.deduplication import cross_source_dedup
        from app.services.quality_filter import quality_score as calc_quality_score
        from app.models import Job as JobModel
        jobs = cross_source_dedup(jobs)
        
        # First pass: check for duplicates and calculate quality scores
        for job_data in jobs:
            try:
                # Calculate quality score
                temp_job = JobModel(
                    title=job_data.title,
                    url=job_data.url,
                    company=job_data.company,
                    location=job_data.location,
                    description=job_data.description,
                    salary_min=job_data.salary_min,
                    salary_max=job_data.salary_max
                )
                quality = calc_quality_score(temp_job)
                
                # Skip low quality jobs (score < 0.6)
                if quality < 0.6:
                    error_count += 1
                    logger.debug(
                        "job_filtered_low_quality",
                        title=job_data.title,
                        quality_score=quality
                    )
                    continue
                
                # Check for duplicates
                is_dup, existing_id = await is_duplicate(self.session, job_data)
                
                if is_dup:
                    duplicate_count += 1
                    # Try to merge metadata
                    await merge_duplicate_metadata(self.session, existing_id, job_data)
                    continue
                
                # Prepare job for bulk insert
                jobs_to_insert.append({
                    'id': uuid.uuid4(),
                    'title': job_data.title,
                    'url': job_data.url,
                    'company': job_data.company,
                    'location': job_data.location,
                    'description': job_data.description,
                    'salary_min': job_data.salary_min,
                    'salary_max': job_data.salary_max,
                    'remote_work': job_data.remote_work,
                    'job_type': job_data.job_type,
                    'quality_score': quality,  # NEW: Add quality score
                    'source_id': self.source.id,
                    'posted_at': job_data.posted_at or datetime.utcnow(),
                    'is_active': True,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                })
                
            except Exception as e:
                error_count += 1
                logger.error(
                    "job_preparation_error",
                    title=job_data.title,
                    error=str(e)
                )
        
        # Bulk insert
        if jobs_to_insert:
            try:
                self.session.bulk_insert_mappings(Job, jobs_to_insert)
                self.session.commit()
                saved_count = len(jobs_to_insert)
                
                logger.info(
                    "jobs_bulk_inserted",
                    count=saved_count,
                    source=self.source_name
                )
                
            except Exception as e:
                error_count += len(jobs_to_insert)
                logger.error(
                    "bulk_insert_error",
                    error=str(e),
                    count=len(jobs_to_insert)
                )
                self.session.rollback()
        
        # Log summary
        log_scraper_event(
            self.session,
            self.source.id,
            LogLevelEnum.INFO,
            f"Scraping completed: {saved_count} saved, {duplicate_count} duplicates, {error_count} errors",
            {
                "saved": saved_count,
                "duplicates": duplicate_count,
                "errors": error_count,
                "total_processed": len(jobs)
            }
        )
        
        return saved_count
    
    async def run(self) -> int:
        """
        Execute the full scraping pipeline.
        
        Returns:
            Number of jobs saved
        """
        # Get source from database
        from sqlalchemy import select
        stmt = select(JobSource).where(JobSource.name == self.source_name)
        result = self.session.execute(stmt)
        self.source = result.scalar_one_or_none()
        
        if not self.source:
            logger.error("source_not_found", source_name=self.source_name)
            return 0
        
        if not self.source.is_active:
            logger.info("source_inactive", source_name=self.source_name)
            return 0
        
        logger.info("scraper_started", source_name=self.source_name)
        
        try:
            # Fetch content
            content = await self.fetch(self.source.url)
            if not content:
                log_scraper_event(
                    self.session,
                    self.source.id,
                    LogLevelEnum.ERROR,
                    "Failed to fetch content",
                    {"url": self.source.url}
                )
                self.source.total_errors += 1
                self.session.commit()
                return 0
            
            # Parse jobs
            jobs = await self.parse(content)
            logger.info("jobs_parsed", count=len(jobs), source=self.source_name)
            
            if not jobs:
                log_scraper_event(
                    self.session,
                    self.source.id,
                    LogLevelEnum.WARNING,
                    "No jobs found",
                    {"url": self.source.url}
                )
                return 0
            
            # Save jobs
            saved_count = await self.save(jobs)
            
            # Update source statistics
            self.source.last_scraped_at = datetime.utcnow()
            self.source.total_jobs_found += saved_count
            
            # Calculate success rate
            total_attempts = self.source.total_jobs_found + self.source.total_errors
            if total_attempts > 0:
                self.source.success_rate = (self.source.total_jobs_found / total_attempts) * 100
            
            self.session.commit()
            
            logger.info(
                "scraper_completed",
                source_name=self.source_name,
                jobs_saved=saved_count
            )
            
            return saved_count
            
        except Exception as e:
            logger.error(
                "scraper_failed",
                source_name=self.source_name,
                error=str(e)
            )
            log_scraper_event(
                self.session,
                self.source.id,
                LogLevelEnum.ERROR,
                f"Scraper failed: {str(e)}",
                {"error_type": type(e).__name__}
            )
            self.source.total_errors += 1
            self.session.commit()
            return 0