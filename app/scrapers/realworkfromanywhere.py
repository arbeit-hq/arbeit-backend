from datetime import datetime
from typing import List
import feedparser
import structlog

from app.scrapers.base import BaseScraper
from app.schemas.job import JobIn

logger = structlog.get_logger()


class RealWorkFromAnywhereScraper(BaseScraper):
    """Scraper for Real Work From Anywhere RSS feed"""
    
    async def parse(self, content: bytes) -> List[JobIn]:
        """Parse Real Work From Anywhere RSS feed"""
        jobs = []
        
        try:
            feed = feedparser.parse(content)
            
            for entry in feed.entries:
                try:
                    title = entry.get('title', '').strip()
                    url = entry.get('link', '').strip()
                    
                    if not title or not url:
                        continue
                    
                    # Parse published date
                    posted_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        posted_at = datetime(*entry.published_parsed[:6])
                    
                    description = entry.get('summary', '')
                    
                    # Extract category from tags or title
                    job_type = None
                    if hasattr(entry, 'tags') and entry.tags:
                        job_type = entry.tags[0].get('term', '') if entry.tags else None
                    
                    # Try to extract company from description or title
                    company = None
                    if ' at ' in title:
                        parts = title.split(' at ')
                        if len(parts) >= 2:
                            company = parts[-1].strip()
                            title = ' at '.join(parts[:-1]).strip()
                    
                    job = JobIn(
                        title=title,
                        url=url,
                        company=company,
                        location="Remote",
                        description=description,
                        remote_work=True,
                        job_type=job_type,
                        posted_at=posted_at,
                        source_name=self.source_name
                    )
                    
                    jobs.append(job)
                    
                except Exception as e:
                    logger.warning(
                        "realworkfromanywhere_entry_parse_error",
                        error=str(e),
                        entry_title=entry.get('title', 'unknown')
                    )
                    continue
            
            logger.info("realworkfromanywhere_parse_complete", jobs_found=len(jobs))
            
        except Exception as e:
            logger.error("realworkfromanywhere_parse_failed", error=str(e))
        
        return jobs


if __name__ == "__main__":
    import asyncio
    from app.core.database import SessionLocal
    
    async def main():
        session = SessionLocal()
        scraper = RealWorkFromAnywhereScraper("RealWorkFromAnywhere", session)
        saved = await scraper.run()
        print(f"Saved {saved} jobs from Real Work From Anywhere")
        session.close()
    
    asyncio.run(main())