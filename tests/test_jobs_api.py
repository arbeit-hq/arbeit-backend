"""
Tests for jobs API endpoints
"""
from fastapi.testclient import TestClient
from app.models import UserPreference
import uuid


def test_search_jobs_no_filters(client: TestClient, test_db, sample_jobs):
    """Test searching jobs without filters"""
    response = client.get("/api/jobs/search")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0


def test_search_jobs_with_keywords(client: TestClient, test_db, sample_jobs):
    """Test searching jobs with keywords"""
    response = client.get("/api/jobs/search?keywords=Python")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    # Verify all results contain Python
    for job in data:
        assert "python" in job["title"].lower() or "python" in (job["description"] or "").lower()


def test_search_jobs_with_location(client: TestClient, test_db, sample_jobs):
    """Test searching jobs with location filter"""
    response = client.get("/api/jobs/search?location=Berlin")
    assert response.status_code == 200
    data = response.json()
    for job in data:
        assert "berlin" in (job["location"] or "").lower() or job["remote_work"] is True


def test_search_jobs_remote_only(client: TestClient, test_db, sample_jobs):
    """Test searching remote jobs only"""
    response = client.get("/api/jobs/search?remote=true")
    assert response.status_code == 200
    data = response.json()
    for job in data:
        assert job["remote_work"] is True


def test_search_jobs_with_salary(client: TestClient, test_db, sample_jobs):
    """Test searching jobs with salary filter"""
    response = client.get("/api/jobs/search?min_salary=50000")
    assert response.status_code == 200
    data = response.json()
    for job in data:
        if job["salary_max"]:
            assert job["salary_max"] >= 50000


def test_search_jobs_pagination(client: TestClient, test_db, sample_jobs):
    """Test job search pagination"""
    response = client.get("/api/jobs/search?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 5


def test_get_matched_jobs_no_auth(client: TestClient):
    """Test matched jobs requires authentication"""
    response = client.get("/api/jobs/matched")
    assert response.status_code == 403


def test_get_matched_jobs_no_preferences(client: TestClient, auth_headers):
    """Test matched jobs without preferences"""
    response = client.get("/api/jobs/matched", headers=auth_headers)
    assert response.status_code == 404


def test_get_matched_jobs_success(client: TestClient, auth_headers, test_user, test_db, sample_jobs):
    """Test getting matched jobs"""
    # Create user preferences
    preference = UserPreference(
        id=uuid.uuid4(),
        user_id=test_user.id,
        keywords=["Python", "Django"],
        location="Berlin",
        salary_min=50000,
        remote_only=False,
        notification_frequency="daily"
    )
    test_db.add(preference)
    test_db.commit()
    
    # Get matched jobs
    response = client.get("/api/jobs/matched", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    if len(data) > 0:
        job = data[0]
        assert "relevance_score" in job
        assert "match_reasons" in job
        assert job["relevance_score"] >= 0.3  # Default min_score


def test_get_matched_jobs_with_min_score(client: TestClient, auth_headers, test_user, test_db, sample_jobs):
    """Test matched jobs with custom min_score"""
    # Create preferences
    preference = UserPreference(
        id=uuid.uuid4(),
        user_id=test_user.id,
        keywords=["Python"],
        notification_frequency="daily"
    )
    test_db.add(preference)
    test_db.commit()
    
    # Get matched jobs with high threshold
    response = client.get("/api/jobs/matched?min_score=0.7", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # All results should have score >= 0.7
    for job in data:
        assert job["relevance_score"] >= 0.7


def test_get_job_by_id(client: TestClient, test_db, sample_jobs):
    """Test getting a specific job by ID"""
    # Get first job from sample
    job = sample_jobs[0]
    
    response = client.get(f"/api/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job.id)
    assert data["title"] == job.title


def test_get_job_not_found(client: TestClient):
    """Test getting non-existent job"""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/jobs/{fake_id}")
    assert response.status_code == 404


def test_get_job_invalid_id(client: TestClient):
    """Test getting job with invalid ID format"""
    response = client.get("/api/jobs/invalid-id")
    assert response.status_code == 400