"""
Seed script to populate job sources in the database.
Run with: python -m app.scripts.seed_sources
"""
from datetime import datetime
import uuid

from app.core.database import SessionLocal
from app.models import JobSource, SourceTypeEnum
import structlog

logger = structlog.get_logger()


SOURCES = [
    {
        "name": "RemoteOK",
        "url": "https://remoteok.com/remote-jobs.rss",
        "source_type": SourceTypeEnum.RSS,
        "priority": 8,
        "scrape_frequency": 7200,  # 2 hours
    },
    {
        "name": "WeWorkRemotely",
        "url": "https://weworkremotely.com/remote-jobs.rss",
        "source_type": SourceTypeEnum.RSS,
        "priority": 8,
        "scrape_frequency": 7200,  # 2 hours
    },
    {
        "name": "Himalayas",
        "url": "https://himalayas.app/jobs/rss",
        "source_type": SourceTypeEnum.RSS,
        "priority": 7,
        "scrape_frequency": 21600,  # 6 hours
    },
    {
        "name": "Jobicy",
        "url": "https://jobicy.com/feed/job_feed",
        "source_type": SourceTypeEnum.RSS,
        "priority": 7,
        "scrape_frequency": 21600,  # 6 hours
    },
    {
        "name": "Remotive",
        "url": "https://remotive.com/remote-jobs/feed",
        "source_type": SourceTypeEnum.RSS,
        "priority": 7,
        "scrape_frequency": 21600,  # 6 hours
    },
    {
        "name": "RealWorkFromAnywhere",
        "url": "https://www.realworkfromanywhere.com/rss.xml",  
        "source_type": SourceTypeEnum.RSS,
        "priority": 6,
        "scrape_frequency": 43200,  # 12 hours
    },
]


def seed_sources():
    """Seed job sources into the database"""
    session = SessionLocal()
    
    try:
        for source_data in SOURCES:
            # Check if source already exists
            existing = session.query(JobSource).filter_by(name=source_data["name"]).first()
            
            if existing:
                logger.info("source_exists", name=source_data["name"])
                continue
            
            # Create new source
            source = JobSource(
                id=uuid.uuid4(),
                name=source_data["name"],
                url=source_data["url"],
                source_type=source_data["source_type"],
                is_active=True,
                priority=source_data["priority"],
                scrape_frequency=source_data["scrape_frequency"],
                created_at=datetime.utcnow(),
                total_jobs_found=0,
                total_errors=0
            )
            
            session.add(source)
            logger.info("source_created", name=source_data["name"])
        
        session.commit()
        logger.info("seed_complete", total_sources=len(SOURCES))
        
    except Exception as e:
        logger.error("seed_failed", error=str(e))
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_sources()