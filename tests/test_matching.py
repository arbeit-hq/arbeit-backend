"""
Tests for job matching engine
"""
import pytest
from datetime import datetime, timedelta
from app.utils.matching import (
    score_keywords, filter_location, filter_salary, 
    filter_job_type, match_job
)
from app.models import Job, UserPreference
import uuid


@pytest.fixture
def sample_user_prefs():
    """Create sample user preferences"""
    return UserPreference(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        keywords=["Python", "Django"],
        excluded_keywords=["PHP"],
        location="Berlin",
        salary_min=50000,
        salary_max=100000,
        remote_only=False,
        job_types=["full-time"],
        notification_frequency="daily"
    )


@pytest.fixture
def python_job():
    """Create a Python job"""
    return Job(
        id=uuid.uuid4(),
        title="Senior Python Developer",
        url="https://example.com/job/1",
        company="Tech Corp",
        location="Berlin, Germany",
        description="We are looking for a Python developer with Django experience.",
        salary_min=60000,
        salary_max=80000,
        remote_work=False,
        job_type="full-time",
        quality_score=0.9,
        posted_at=datetime.utcnow()
    )


@pytest.fixture
def java_job():
    """Create a Java job"""
    return Job(
        id=uuid.uuid4(),
        title="Java Developer",
        url="https://example.com/job/2",
        company="Enterprise Inc",
        location="Munich, Germany",
        description="Looking for Java Spring developers.",
        salary_min=55000,
        salary_max=75000,
        remote_work=False,
        job_type="full-time",
        quality_score=0.8
    )


@pytest.fixture
def remote_python_job():
    """Create a remote Python job"""
    return Job(
        id=uuid.uuid4(),
        title="Remote Python Engineer",
        url="https://example.com/job/3",
        company="Remote Co",
        location="Remote",
        description="Python and Django development for remote team.",
        salary_min=70000,
        salary_max=90000,
        remote_work=True,
        job_type="full-time",
        quality_score=0.85,
        posted_at=datetime.utcnow() - timedelta(days=2)
    )


def test_keyword_matching_positive(python_job, sample_user_prefs):
    """Test keyword matching with matching job"""
    score = score_keywords(python_job, sample_user_prefs)
    assert score > 0.5  # Should match Python and Django


def test_keyword_matching_negative(java_job, sample_user_prefs):
    """Test keyword matching with non-matching job"""
    score = score_keywords(java_job, sample_user_prefs)
    assert score == 0.0  # No Python or Django keywords


def test_excluded_keywords(sample_user_prefs):
    """Test excluded keywords filter"""
    php_job = Job(
        id=uuid.uuid4(),
        title="PHP Developer",
        url="https://example.com/job/4",
        description="Looking for PHP and Python developers.",
        quality_score=0.8
    )
    score = score_keywords(php_job, sample_user_prefs)
    assert score == 0.0  # Should be excluded due to PHP


def test_location_filter_exact(python_job, sample_user_prefs):
    """Test location filter with exact match"""
    result = filter_location(python_job, sample_user_prefs)
    assert result is True  # Berlin matches "Berlin, Germany"


def test_location_filter_mismatch(java_job, sample_user_prefs):
    """Test location filter with mismatch"""
    result = filter_location(java_job, sample_user_prefs)
    assert result is False  # Munich doesn't match Berlin


def test_location_filter_no_preference():
    """Test location filter with no preference"""
    prefs = UserPreference(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        keywords=["Python"],
        remote_only=False
    )
    job = Job(
        id=uuid.uuid4(),
        title="Developer",
        url="https://example.com/job",
        location="Anywhere"
    )
    result = filter_location(job, prefs)
    assert result is True  # No location preference, all pass


def test_remote_filter(remote_python_job):
    """Test remote-only filter"""
    prefs = UserPreference(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        keywords=["Python"],
        remote_only=True
    )
    result = filter_location(remote_python_job, prefs)
    assert result is True  # Remote job passes remote filter


def test_remote_filter_rejects_non_remote(python_job):
    """Test remote-only filter rejects non-remote jobs"""
    prefs = UserPreference(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        keywords=["Python"],
        remote_only=True
    )
    result = filter_location(python_job, prefs)
    assert result is False  # Non-remote job fails remote filter


def test_salary_filter_in_range(python_job, sample_user_prefs):
    """Test salary filter with job in range"""
    result = filter_salary(python_job, sample_user_prefs)
    assert result is True  # 60k-80k is within 50k-100k


def test_salary_filter_too_low(sample_user_prefs):
    """Test salary filter with job below minimum"""
    low_salary_job = Job(
        id=uuid.uuid4(),
        title="Junior Developer",
        url="https://example.com/job",
        salary_min=30000,
        salary_max=40000
    )
    result = filter_salary(low_salary_job, sample_user_prefs)
    assert result is False  # 40k max is below 50k min


def test_salary_filter_no_preference():
    """Test salary filter with no preference"""
    prefs = UserPreference(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        keywords=["Python"]
    )
    job = Job(
        id=uuid.uuid4(),
        title="Developer",
        url="https://example.com/job",
        salary_min=30000
    )
    result = filter_salary(job, prefs)
    assert result is True  # No salary preference, all pass


def test_salary_filter_no_job_salary(sample_user_prefs):
    """Test salary filter with job having no salary"""
    no_salary_job = Job(
        id=uuid.uuid4(),
        title="Developer",
        url="https://example.com/job"
    )
    result = filter_salary(no_salary_job, sample_user_prefs)
    assert result is True  # Jobs without salary data pass filter


def test_job_type_filter(python_job, sample_user_prefs):
    """Test job type filter"""
    result = filter_job_type(python_job, sample_user_prefs)
    assert result is True  # full-time matches


def test_job_type_filter_mismatch(sample_user_prefs):
    """Test job type filter with mismatch"""
    contract_job = Job(
        id=uuid.uuid4(),
        title="Contract Developer",
        url="https://example.com/job",
        job_type="contract"
    )
    result = filter_job_type(contract_job, sample_user_prefs)
    assert result is False  # contract doesn't match full-time


def test_match_job_integration(python_job, sample_user_prefs):
    """Test full matching with all filters"""
    score, reasons = match_job(python_job, sample_user_prefs)
    assert score > 0.3  # Should have decent match
    assert "Python" in reasons["matched_keywords"]
    assert "Django" in reasons["matched_keywords"]
    assert "location" in reasons["filters_passed"]
    assert "salary" in reasons["filters_passed"]


def test_match_job_low_quality():
    """Test matching rejects low quality jobs"""
    low_quality_job = Job(
        id=uuid.uuid4(),
        title="Python Developer",
        url="https://example.com/job",
        quality_score=0.4  # Below threshold
    )
    prefs = UserPreference(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        keywords=["Python"]
    )
    score, reasons = match_job(low_quality_job, prefs)
    assert score == 0.0  # Low quality jobs get 0 score


def test_match_job_with_bonuses(remote_python_job, sample_user_prefs):
    """Test matching with bonus scoring"""
    # Make it remote-only preference
    sample_user_prefs.remote_only = True
    
    score, reasons = match_job(remote_python_job, sample_user_prefs)
    assert score > 0.5  # Should have good score with bonuses
    assert reasons["has_salary"] is True
    assert reasons["is_remote"] is True
    assert reasons["is_recent"] is True  # Posted 2 days ago
    assert reasons["high_quality"] is True  # Quality score 0.85


def test_match_reasons_generation(python_job, sample_user_prefs):
    """Test match reasons are correctly generated"""
    score, reasons = match_job(python_job, sample_user_prefs)
    
    assert "keyword_score" in reasons
    assert "matched_keywords" in reasons
    assert "filters_passed" in reasons
    assert "has_salary" in reasons
    assert isinstance(reasons["matched_keywords"], list)
    assert len(reasons["matched_keywords"]) > 0


def test_no_keywords_preference():
    """Test matching with no keyword preference"""
    prefs = UserPreference(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        keywords=[],
        location="Berlin"
    )
    job = Job(
        id=uuid.uuid4(),
        title="Any Job",
        url="https://example.com/job",
        location="Berlin",
        quality_score=0.8
    )
    score, reasons = match_job(job, prefs)
    assert score > 0.0  # Should still match based on location