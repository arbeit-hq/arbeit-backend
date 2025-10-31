import pytest
from unittest.mock import AsyncMock, patch

from app.scrapers.remoteok import RemoteOKScraper
from app.models import Job
from sqlalchemy import select


@pytest.mark.asyncio
async def test_complete_pipeline_end_to_end(test_db, sample_job_source):
    """Test complete pipeline: fetch → parse → dedupe → save → verify"""
    scraper = RemoteOKScraper("RemoteOK", test_db)
    scraper.source = sample_job_source
    
    # Mock RSS feed with multiple jobs (including duplicates)
    rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item>
                <title>Senior Python Developer at TechCorp</title>
                <link>https://remoteok.io/job/123</link>
                <pubDate>Mon, 01 Oct 2025 12:00:00 GMT</pubDate>
                <description>Great opportunity</description>
            </item>
            <item>
                <title>Python Engineer at TechCorp</title>
                <link>https://remoteok.io/job/124</link>
                <pubDate>Mon, 01 Oct 2025 13:00:00 GMT</pubDate>
                <description>Similar opportunity</description>
            </item>
            <item>
                <title>Senior Python Developer at TechCorp</title>
                <link>https://remoteok.io/job/123</link>
                <pubDate>Mon, 01 Oct 2025 12:00:00 GMT</pubDate>
                <description>Duplicate job</description>
            </item>
        </channel>
    </rss>
    """
    
    # Mock fetch
    with patch.object(scraper, 'fetch', new=AsyncMock(return_value=rss_content)):
        saved_count = await scraper.run()
    
    # Verify deduplication worked (3 jobs, 1 duplicate = 2 saved)
    assert saved_count == 2
    
    # Verify jobs in database
    stmt = select(Job).where(Job.source_id == sample_job_source.id)
    result = test_db.execute(stmt)
    jobs = result.scalars().all()
    
    assert len(jobs) == 2
    
    # Verify job data
    job_titles = {job.title for job in jobs}
    assert "Senior Python Developer" in job_titles
    assert "Python Engineer" in job_titles
    
    # Verify source statistics updated
    assert sample_job_source.last_scraped_at is not None
    assert sample_job_source.total_jobs_found == 2
    assert sample_job_source.success_rate > 0


@pytest.mark.asyncio
async def test_pipeline_with_errors(test_db, sample_job_source):
    """Test pipeline handles errors gracefully"""
    scraper = RemoteOKScraper("RemoteOK", test_db)
    scraper.source = sample_job_source
    
    # Mock fetch failure
    with patch.object(scraper, 'fetch', new=AsyncMock(return_value=None)):
        saved_count = await scraper.run()
    
    # Should handle gracefully
    assert saved_count == 0
    assert sample_job_source.total_errors == 1


@pytest.mark.asyncio
async def test_pipeline_performance(test_db, sample_job_source):
    """Test pipeline can handle large batches efficiently"""
    scraper = RemoteOKScraper("RemoteOK", test_db)
    scraper.source = sample_job_source
    
    # Generate large RSS feed (100 jobs)
    items = []
    for i in range(100):
        items.append(f"""
            <item>
                <title>Job {i} at Company {i % 10}</title>
                <link>https://remoteok.io/job/{i}</link>
                <pubDate>Mon, 01 Oct 2025 12:00:00 GMT</pubDate>
                <description>Job description {i}</description>
            </item>
        """)
    
    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            {''.join(items)}
        </channel>
    </rss>
    """.encode()
    
    import time
    start_time = time.time()
    
    with patch.object(scraper, 'fetch', new=AsyncMock(return_value=rss_content)):
        saved_count = await scraper.run()
    
    elapsed_time = time.time() - start_time
    
    # Should complete in reasonable time (< 10 seconds for 100 jobs)
    assert elapsed_time < 10
    assert saved_count == 100
    
    # Verify bulk insert worked
    stmt = select(Job).where(Job.source_id == sample_job_source.id)
    result = test_db.execute(stmt)
    jobs = result.scalars().all()
    assert len(jobs) == 100