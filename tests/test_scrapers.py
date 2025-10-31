import pytest

from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.weworkremotely import WeWorkRemotelyScraper


@pytest.mark.asyncio
async def test_remoteok_scraper_success(test_db, sample_job_source):
    """Test RemoteOK scraper with valid RSS feed"""
    scraper = RemoteOKScraper("RemoteOK", test_db)
    
    # Mock RSS feed content
    rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item>
                <title>Senior Python Developer at TechCorp</title>
                <link>https://remoteok.io/job/123</link>
                <pubDate>Mon, 01 Oct 2025 10:00:00 GMT</pubDate>
                <description>Great remote opportunity</description>
            </item>
        </channel>
    </rss>
    """
    
    jobs = await scraper.parse(rss_content)
    
    assert len(jobs) > 0
    assert jobs[0].title == "Senior Python Developer"
    assert jobs[0].company == "TechCorp"
    assert jobs[0].remote_work is True


@pytest.mark.asyncio
async def test_weworkremotely_scraper_success(test_db, sample_job_source):
    """Test WeWorkRemotely scraper with valid RSS feed"""
    scraper = WeWorkRemotelyScraper("WeWorkRemotely", test_db)
    
    rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item>
                <title>TechCorp: Backend Engineer (Programming)</title>
                <link>https://weworkremotely.com/job/456</link>
                <pubDate>Mon, 01 Oct 2025 11:00:00 GMT</pubDate>
                <description>Backend position</description>
            </item>
        </channel>
    </rss>
    """
    
    jobs = await scraper.parse(rss_content)
    
    assert len(jobs) > 0
    assert jobs[0].company == "TechCorp"
    assert jobs[0].job_type == "Programming"