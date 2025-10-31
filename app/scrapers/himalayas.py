from datetime import datetime
from typing import List
import feedparser
import structlog

from app.scrapers.base import BaseScraper
from app.schemas.job import JobIn

logger = structlog.get_logger()


class HimalayasScraper(BaseScraper):
    """Scraper for Himalayas RSS feed"""
    
    async def parse(self, content: bytes) -> List[JobIn]:
        """Parse Himalayas RSS feed"""
        jobs = []
        
        try:
            feed = feedparser.parse(content)
            
            for entry in feed.entries:
                try:
                    # Extract job details
                    title = entry.get('title', '').strip()
                    url = entry.get('link', '').strip()
                    
                    if not title or not url:
                        continue
                    
                    # Parse published date
                    posted_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        posted_at = datetime(*entry.published_parsed[:6])
                    
                    # Extract description
                    description = entry.get('summary', '')
                    
                    # Try to extract company from title or description
                    company = None
                    if ' at ' in title:
                        parts = title.split(' at ')
                        if len(parts) >= 2:
                            company = parts[-1].strip()
                            title = ' at '.join(parts[:-1]).strip()
                    
                    # Himalayas jobs are typically remote
                    remote_work = True
                    
                    job = JobIn(
                        title=title,
                        url=url,
                        company=company,
                        location="Remote",
                        description=description,
                        remote_work=remote_work,
                        posted_at=posted_at,
                        source_name=self.source_name
                    )
                    
                    jobs.append(job)
                    
                except Exception as e:
                    logger.warning(
                        "himalayas_entry_parse_error",
                        error=str(e),
                        entry_title=entry.get('title', 'unknown')
                    )
                    continue
            
            logger.info("himalayas_parse_complete", jobs_found=len(jobs))
            
        except Exception as e:
            logger.error("himalayas_parse_failed", error=str(e))
        
        return jobs


# CLI entrypoint for testing
if __name__ == "__main__":
    import asyncio
    from app.core.database import SessionLocal
    
    async def main():
        session = SessionLocal()
        scraper = HimalayasScraper("Himalayas", session)
        saved = await scraper.run()
        print(f"Saved {saved} jobs from Himalayas")
        session.close()
    
    asyncio.run(main())