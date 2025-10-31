import pytest
from unittest.mock import AsyncMock, patch

from app.scrapers.remoteok import RemoteOKScraper


@pytest.mark.asyncio
async def test_full_scraping_pipeline(test_db, sample_job_source):
    """Test complete scraping pipeline from fetch to save"""
    scraper = RemoteOKScraper("RemoteOK", test_db)
    scraper.source = sample_job_source
    
    # Mock fetch to return sample RSS
    rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item>
                <title>Python Developer at StartupCo</title>
                <link>https://remoteok.io/job/789</link>
                <pubDate>Mon, 01 Oct 2025 12:00:00 GMT</pubDate>
                <description>Exciting startup opportunity</description>
            </item>
        </channel>
    </rss>
    """
    
    with patch.object(scraper, 'fetch', new=AsyncMock(return_value=rss_content)):
        saved_count = await scraper.run()
    
    assert saved_count > 0
    
    # Verify job was saved to database
    from sqlalchemy import select
    from app.models import Job
    
    stmt = select(Job).where(Job.source_id == sample_job_source.id)
    result = test_db.execute(stmt)
    jobs = result.scalars().all()
    
    assert len(jobs) == saved_count
    assert jobs[0].title == "Python Developer"
    assert jobs[0].company == "StartupCo"