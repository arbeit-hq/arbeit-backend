"""
Tests for quality filtering service
"""
import pytest
from app.services.quality_filter import is_spam, quality_score, filter_jobs_by_quality
from app.models import Job
import uuid


@pytest.fixture
def good_job():
    """Create a good quality job"""
    return Job(
        id=uuid.uuid4(),
        title="Senior Python Developer",
        url="https://example.com/job/123",
        company="Tech Corp",
        location="Berlin, Germany",
        description="We are looking for an experienced Python developer to join our team. " * 5,
        salary_min=60000,
        salary_max=80000,
        remote_work=True
    )


@pytest.fixture
def spam_job():
    """Create a spam job"""
    return Job(
        id=uuid.uuid4(),
        title="Make Money Fast from Home",
        url="https://t.me/scam",
        company="Scam Company Inc",
        location="Remote",
        description="Click here to earn money from home! No experience needed!",
        remote_work=True
    )


@pytest.fixture
def low_quality_job():
    """Create a low quality job"""
    return Job(
        id=uuid.uuid4(),
        title="Job",
        url="https://example.com/job/456",
        company="",
        location="",
        description="Short desc",
        remote_work=False
    )


def test_is_spam_detects_suspicious_keywords(spam_job):
    """Test spam detection with suspicious keywords"""
    is_spam_result, reason = is_spam(spam_job)
    assert is_spam_result is True
    assert "keyword" in reason.lower()


def test_is_spam_detects_suspicious_urls():
    """Test spam detection with suspicious URLs"""
    job = Job(
        id=uuid.uuid4(),
        title="Great Job Opportunity",
        url="https://bit.ly/scam123",
        company="Company",
        description="A legitimate job description that is long enough to pass other checks." * 3
    )
    is_spam_result, reason = is_spam(job)
    assert is_spam_result is True
    assert "url" in reason.lower()


def test_is_spam_detects_excessive_caps():
    """Test spam detection with excessive uppercase"""
    job = Job(
        id=uuid.uuid4(),
        title="URGENT HIRING NOW APPLY TODAY",
        url="https://example.com/job",
        company="Company",
        description="A legitimate job description that is long enough to pass other checks." * 3
    )
    is_spam_result, reason = is_spam(job)
    assert is_spam_result is True
    assert "uppercase" in reason.lower()


def test_is_spam_allows_good_jobs(good_job):
    """Test that good jobs are not flagged as spam"""
    is_spam_result, reason = is_spam(good_job)
    assert is_spam_result is False
    assert reason == ""


def test_quality_score_good_job(good_job):
    """Test quality score for good job"""
    score = quality_score(good_job)
    assert score >= 0.8  # Has company, description, location, salary, proper title


def test_quality_score_low_quality(low_quality_job):
    """Test quality score for low quality job"""
    score = quality_score(low_quality_job)
    assert score < 0.6  # Missing company, location, short description, no salary


def test_quality_score_partial():
    """Test quality score with partial information"""
    job = Job(
        id=uuid.uuid4(),
        title="Python Developer",
        url="https://example.com/job",
        company="Tech Corp",
        description="We need a Python developer." * 10,
        location="",
        salary_min=None,
        salary_max=None
    )
    score = quality_score(job)
    assert 0.5 <= score <= 0.7  # Has company, description, title but missing location and salary


def test_filter_jobs_by_quality():
    """Test filtering jobs by quality"""
    jobs = [
        Job(
            id=uuid.uuid4(),
            title="Senior Developer",
            url=f"https://example.com/job/{i}",
            company="Tech Corp",
            location="Berlin",
            description="Great opportunity." * 20,
            salary_min=50000
        ) for i in range(3)
    ]
    
    # Add a low quality job
    jobs.append(Job(
        id=uuid.uuid4(),
        title="Job",
        url="https://example.com/bad",
        company="",
        description="Bad"
    ))
    
    # Add a spam job
    jobs.append(Job(
        id=uuid.uuid4(),
        title="MAKE MONEY FAST",
        url="https://t.me/scam",
        description="Click here to earn money!"
    ))
    
    filtered = filter_jobs_by_quality(jobs, min_score=0.6)
    assert len(filtered) == 3  # Only the 3 good jobs


def test_filter_jobs_empty_list():
    """Test filtering empty job list"""
    filtered = filter_jobs_by_quality([], min_score=0.6)
    assert len(filtered) == 0


def test_is_spam_short_description():
    """Test spam detection with very short description"""
    job = Job(
        id=uuid.uuid4(),
        title="Job Title",
        url="https://example.com/job",
        company="Company",
        description="Short"
    )
    is_spam_result, reason = is_spam(job)
    assert is_spam_result is True
    assert "short" in reason.lower()