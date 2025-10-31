import pytest
from datetime import datetime

from app.utils.deduplication import is_duplicate, cross_source_dedup
from app.models import Job
from app.schemas.job import JobIn


@pytest.mark.asyncio
async def test_url_duplicate_detection(test_db, sample_job_source, sample_job_data):
    """Test URL-based duplicate detection"""
    # Create existing job
    existing_job = Job(
        title="Existing Job",
        url=sample_job_data.url,  # Same URL
        company="Company",
        source_id=sample_job_source.id,
        posted_at=datetime.utcnow(),
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db.add(existing_job)
    test_db.commit()
    
    # Check for duplicate
    is_dup, job_id = await is_duplicate(test_db, sample_job_data)
    
    assert is_dup is True
    assert job_id == str(existing_job.id)


@pytest.mark.asyncio
async def test_fuzzy_title_matching(test_db, sample_job_source):
    """Test fuzzy matching on title and company"""
    # Create existing job with similar title
    existing_job = Job(
        title="Senior Python Engineer",  # Similar to "Senior Python Developer"
        url="https://example.com/different-url",
        company="Test Company",
        source_id=sample_job_source.id,
        posted_at=datetime.utcnow(),
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db.add(existing_job)
    test_db.commit()
    
    job_data = JobIn(
        title="Senior Python Developer",
        url="https://example.com/another-url",
        company="Test Company",
        source_name="TestSource"
    )
    
    is_dup, job_id = await is_duplicate(test_db, job_data, fuzzy_threshold=85)
    
    assert is_dup is True


def test_cross_source_deduplication():
    """Test batch deduplication"""
    jobs = [
        JobIn(
            title="Python Developer",
            url="https://example.com/job1",
            company="Company A",
            source_name="Source1"
        ),
        JobIn(
            title="Python Developer",  # Duplicate title
            url="https://example.com/job1",  # Duplicate URL
            company="Company A",
            source_name="Source2"
        ),
        JobIn(
            title="Java Developer",
            url="https://example.com/job2",
            company="Company B",
            source_name="Source1"
        ),
    ]
    
    unique_jobs = cross_source_dedup(jobs)
    
    assert len(unique_jobs) == 2
    assert unique_jobs[0].title == "Python Developer"
    assert unique_jobs[1].title == "Java Developer"