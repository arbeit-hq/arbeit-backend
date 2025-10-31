from datetime import datetime
from typing import List
import feedparser
import structlog

from app.scrapers.base import BaseScraper
from app.schemas.job import JobIn

logger = structlog.get_logger()


class WeWorkRemotelyScraper(BaseScraper):
    """Scraper for We Work Remotely RSS feed"""
    
    async def parse(self, content: bytes) -> List[JobIn]:
        """Parse We Work Remotely RSS feed"""
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
                    
                    # Extract company and category from title
                    # Format: "Company: Job Title (Category)"
                    company = None
                    job_type = None
                    
                    if ':' in title:
                        parts = title.split(':', 1)
                        company = parts[0].strip()
                        title = parts[1].strip()
                    
                    if '(' in title and ')' in title:
                        category_start = title.rfind('(')
                        category_end = title.rfind(')')
                        job_type = title[category_start+1:category_end].strip()
                        title = title[:category_start].strip()
                    
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
                        "weworkremotely_entry_parse_error",
                        error=str(e),
                        entry_title=entry.get('title', 'unknown')
                    )
                    continue
            
            logger.info("weworkremotely_parse_complete", jobs_found=len(jobs))
            
        except Exception as e:
            logger.error("weworkremotely_parse_failed", error=str(e))
        
        return jobs


if __name__ == "__main__":
    import asyncio
    from app.core.database import SessionLocal
    
    async def main():
        session = SessionLocal()
        scraper = WeWorkRemotelyScraper("WeWorkRemotely", session)
        saved = await scraper.run()
        print(f"Saved {saved} jobs from We Work Remotely")
        session.close()
    
    asyncio.run(main())