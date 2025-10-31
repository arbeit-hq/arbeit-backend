import asyncio
from celery import Task
from celery.utils.log import get_task_logger
import structlog

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.source_manager import SourceRegistry
from app.utils.logging import detect_source_degradation

logger = get_task_logger(__name__)
struct_logger = structlog.get_logger()


class DatabaseTask(Task):
    """Base task with database session management"""
    _session = None
    
    @property
    def session(self):
        if self._session is None:
            self._session = SessionLocal()
        return self._session
    
    def after_return(self, *args, **kwargs):
        if self._session is not None:
            self._session.close()
            self._session = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def run_scraper(self, source_name: str) -> dict:
    """
    Run a specific scraper.
    
    Args:
        source_name: Name of the source to scrape
        
    Returns:
        Dictionary with scraping results
    """
    logger.info(f"Starting scraper for {source_name}")
    
    try:
        registry = SourceRegistry(self.session)
        scraper = registry.get_scraper(source_name)
        
        if not scraper:
            logger.error(f"Scraper not found: {source_name}")
            return {
                "success": False,
                "source_name": source_name,
                "error": "Scraper not found"
            }
        
        # Run scraper (async)
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        jobs_saved = loop.run_until_complete(scraper.run())
        
        logger.info(f"Scraper completed for {source_name}: {jobs_saved} jobs saved")
        
        return {
            "success": True,
            "source_name": source_name,
            "jobs_saved": jobs_saved
        }
        
    except Exception as e:
        logger.error(f"Scraper failed for {source_name}: {str(e)}")
        raise


@celery_app.task(bind=True, base=DatabaseTask)
def run_all_scrapers(self, max_concurrent: int = 3) -> dict:
    """
    Run all active scrapers sequentially (simplified version).
    
    Args:
        max_concurrent: Maximum number of concurrent scrapers (not used in this version)
        
    Returns:
        Dictionary with overall results
    """
    logger.info("Starting all scrapers")
    
    try:
        registry = SourceRegistry(self.session)
        active_sources = registry.get_active_sources()
        
        if not active_sources:
            logger.warning("No active sources found")
            return {
                "success": True,
                "total_sources": 0,
                "results": []
            }
        
        results = []
        
        # Run scrapers sequentially to avoid complexity
        for source in active_sources:
            try:
                # Call run_scraper directly
                result = run_scraper(source.name)
                results.append(result)
                logger.info(f"Completed {source.name}: {result}")
            except Exception as e:
                logger.error(f"Failed to scrape {source.name}: {str(e)}")
                results.append({
                    "success": False,
                    "source_name": source.name,
                    "error": str(e)
                })
        
        total_jobs = sum(r.get('jobs_saved', 0) for r in results if r.get('success'))
        
        logger.info(f"All scrapers completed: {total_jobs} total jobs saved")
        
        return {
            "success": True,
            "total_sources": len(active_sources),
            "total_jobs_saved": total_jobs,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to run all scrapers: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "total_sources": 0,
            "results": []
        }


@celery_app.task(bind=True, base=DatabaseTask)
def health_check_task(self) -> dict:
    """
    Perform health check on all sources.
    
    Returns:
        Dictionary with health check results
    """
    logger.info("Running health check")
    
    try:
        registry = SourceRegistry(self.session)
        health_data = registry.get_source_health()
        
        # Check for degraded sources
        degraded_sources = []
        for source in health_data:
            if detect_source_degradation(self.session, source['id']):
                degraded_sources.append(source['name'])
        
        if degraded_sources:
            logger.warning(f"Degraded sources detected: {', '.join(degraded_sources)}")
        
        return {
            "success": True,
            "total_sources": len(health_data),
            "degraded_sources": degraded_sources,
            "health_data": health_data
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }