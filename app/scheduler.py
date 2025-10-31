from datetime import timedelta
import structlog

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.source_manager import SourceRegistry

logger = structlog.get_logger()


def setup_dynamic_schedule():
    """
    Setup dynamic Celery Beat schedule based on source configurations.
    This should be called on worker startup.
    """
    session = SessionLocal()
    
    try:
        registry = SourceRegistry(session)
        active_sources = registry.get_active_sources()
        
        schedule_dict = {}
        
        for source in active_sources:
            # Create schedule entry for each source
            task_name = f'scrape-{source.name.lower().replace(" ", "-")}'
            
            schedule_dict[task_name] = {
                'task': 'app.tasks.run_scraper',
                'schedule': timedelta(seconds=source.scrape_frequency),
                'args': (source.name,),
                'options': {
                    'expires': source.scrape_frequency / 2,  # Expire if not run within half the frequency
                }
            }
            
            logger.info(
                "schedule_added",
                source_name=source.name,
                frequency_seconds=source.scrape_frequency
            )
        
        # Add health check task
        schedule_dict['health-check'] = {
            'task': 'app.tasks.health_check_task',
            'schedule': timedelta(minutes=30),
        }
        
        # Update Celery Beat schedule
        celery_app.conf.beat_schedule = schedule_dict
        
        logger.info(
            "dynamic_schedule_setup_complete",
            total_tasks=len(schedule_dict)
        )
        
    except Exception as e:
        logger.error("dynamic_schedule_setup_failed", error=str(e))
    finally:
        session.close()


# Call setup on module import
setup_dynamic_schedule()