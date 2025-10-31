from typing import Dict, List, Type, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
import structlog

from app.models import JobSource
from app.scrapers.base import BaseScraper
from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.weworkremotely import WeWorkRemotelyScraper
from app.scrapers.himalayas import HimalayasScraper
from app.scrapers.jobicy import JobicyScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.realworkfromanywhere import RealWorkFromAnywhereScraper

logger = structlog.get_logger()


class SourceRegistry:
    """Registry for managing job sources and scrapers"""
    
    # Map source names to scraper classes
    SCRAPERS: Dict[str, Type[BaseScraper]] = {
        "RemoteOK": RemoteOKScraper,
        "WeWorkRemotely": WeWorkRemotelyScraper,
        "Himalayas": HimalayasScraper,
        "Jobicy": JobicyScraper,
        "Remotive": RemotiveScraper,
        "RealWorkFromAnywhere": RealWorkFromAnywhereScraper,
    }
    
    def __init__(self, session: Session):
        """Initialize source registry with database session"""
        self.session = session
    
    def get_scraper(self, source_name: str) -> Optional[BaseScraper]:
        """
        Get scraper instance for a source.
        
        Args:
            source_name: Name of the source
            
        Returns:
            Scraper instance or None if not found
        """
        scraper_class = self.SCRAPERS.get(source_name)
        if not scraper_class:
            logger.warning("scraper_not_found", source_name=source_name)
            return None
        
        return scraper_class(source_name, self.session)
    
    def get_active_sources(self) -> List[JobSource]:
        """
        Get all active job sources from database.
        
        Returns:
            List of active JobSource objects
        """
        stmt = select(JobSource).where(JobSource.is_active)  # FIX: Remove == True
        result = self.session.execute(stmt)
        sources = result.scalars().all()
        
        logger.info("active_sources_fetched", count=len(sources))
        return sources
    
    def update_source_stats(
        self,
        source_id: str,
        jobs_found: int,
        errors: int = 0
    ) -> None:
        """
        Update source statistics after scraping.
        
        Args:
            source_id: ID of the source
            jobs_found: Number of jobs found
            errors: Number of errors encountered
        """
        stmt = select(JobSource).where(JobSource.id == source_id)
        result = self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if not source:
            logger.warning("source_not_found_for_stats", source_id=source_id)
            return
        
        source.total_jobs_found += jobs_found
        source.total_errors += errors
        source.last_scraped_at = datetime.utcnow()
        
        # Calculate success rate
        total_attempts = source.total_jobs_found + source.total_errors
        if total_attempts > 0:
            source.success_rate = (source.total_jobs_found / total_attempts) * 100
        
        self.session.commit()
        
        logger.info(
            "source_stats_updated",
            source_id=source_id,
            jobs_found=jobs_found,
            errors=errors,
            success_rate=source.success_rate
        )
    
    def get_source_health(self) -> List[Dict]:
        """
        Get health status for all sources.
        
        Returns:
            List of dictionaries with source health information
        """
        sources = self.get_active_sources()
        health_data = []
        
        for source in sources:
            health_data.append({
                "id": str(source.id),
                "name": source.name,
                "is_active": source.is_active,
                "last_scraped_at": source.last_scraped_at.isoformat() if source.last_scraped_at else None,
                "total_jobs_found": source.total_jobs_found,
                "total_errors": source.total_errors,
                "success_rate": round(source.success_rate, 2) if source.success_rate else 0,
                "scrape_frequency": source.scrape_frequency,
                "priority": source.priority
            })
        
        return health_data
    
    def enable_source(self, source_id: str) -> bool:
        """
        Enable a job source.
        
        Args:
            source_id: ID of the source
            
        Returns:
            True if successful, False otherwise
        """
        stmt = select(JobSource).where(JobSource.id == source_id)
        result = self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if not source:
            logger.warning("source_not_found_for_enable", source_id=source_id)
            return False
        
        source.is_active = True
        self.session.commit()
        
        logger.info("source_enabled", source_id=source_id, name=source.name)
        return True
    
    def disable_source(self, source_id: str) -> bool:
        """
        Disable a job source.
        
        Args:
            source_id: ID of the source
            
        Returns:
            True if successful, False otherwise
        """
        stmt = select(JobSource).where(JobSource.id == source_id)
        result = self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if not source:
            logger.warning("source_not_found_for_disable", source_id=source_id)
            return False
        
        source.is_active = False
        self.session.commit()
        
        logger.info("source_disabled", source_id=source_id, name=source.name)
        return True
    
    @classmethod
    def get_available_scrapers(cls) -> List[str]:
        """
        Get list of available scraper names.
        
        Returns:
            List of scraper names
        """
        return list(cls.SCRAPERS.keys())