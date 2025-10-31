"""
Tests for preferences API endpoints
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_headers(test_user, test_db):
    """Get authentication headers for test user"""
    from app.core.security import create_access_token
    token = create_access_token({"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


def test_create_preferences(client: TestClient, auth_headers, test_db):
    """Test creating user preferences"""
    preference_data = {
        "keywords": ["Python", "Django"],
        "excluded_keywords": ["PHP"],
        "location": "Berlin",
        "salary_min": 50000,
        "salary_max": 100000,
        "remote_only": False,
        "job_types": ["full-time"],
        "notification_frequency": "daily"
    }
    
    response = client.post("/api/preferences", json=preference_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["keywords"] == ["Python", "Django"]
    assert data["location"] == "Berlin"
    assert data["salary_min"] == 50000


def test_get_preferences_not_found(client: TestClient, auth_headers):
    """Test getting preferences when none exist"""
    response = client.get("/api/preferences", headers=auth_headers)
    assert response.status_code == 404


def test_get_preferences_success(client: TestClient, auth_headers, test_user, test_db):
    """Test getting existing preferences"""
    # Create preferences first
    preference_data = {
        "keywords": ["Python"],
        "location": "Berlin",
        "salary_min": 50000
    }
    client.post("/api/preferences", json=preference_data, headers=auth_headers)
    
    # Get preferences
    response = client.get("/api/preferences", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == ["Python"]


def test_update_preferences(client: TestClient, auth_headers, test_user, test_db):
    """Test updating existing preferences"""
    # Create initial preferences
    initial_data = {
        "keywords": ["Python"],
        "location": "Berlin"
    }
    client.post("/api/preferences", json=initial_data, headers=auth_headers)
    
    # Update preferences
    update_data = {
        "keywords": ["Python", "Django", "React"],
        "location": "Munich",
        "salary_min": 60000
    }
    response = client.post("/api/preferences", json=update_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert len(data["keywords"]) == 3
    assert data["location"] == "Munich"


def test_partial_update_preferences(client: TestClient, auth_headers, test_user, test_db):
    """Test partially updating preferences"""
    # Create initial preferences
    initial_data = {
        "keywords": ["Python"],
        "location": "Berlin",
        "salary_min": 50000
    }
    client.post("/api/preferences", json=initial_data, headers=auth_headers)
    
    # Partial update
    patch_data = {
        "salary_min": 60000
    }
    response = client.patch("/api/preferences", json=patch_data, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["salary_min"] == 60000
    assert data["keywords"] == ["Python"]  # Unchanged
    assert data["location"] == "Berlin"  # Unchanged


def test_delete_preferences(client: TestClient, auth_headers, test_user, test_db):
    """Test deleting preferences"""
    # Create preferences
    preference_data = {
        "keywords": ["Python"],
        "location": "Berlin"
    }
    client.post("/api/preferences", json=preference_data, headers=auth_headers)
    
    # Delete preferences
    response = client.delete("/api/preferences", headers=auth_headers)
    assert response.status_code == 204
    
    # Verify deleted
    response = client.get("/api/preferences", headers=auth_headers)
    assert response.status_code == 404


def test_create_preferences_validation_error(client: TestClient, auth_headers):
    """Test preferences validation"""
    # Missing required keywords
    invalid_data = {
        "location": "Berlin"
    }
    response = client.post("/api/preferences", json=invalid_data, headers=auth_headers)
    assert response.status_code == 422
    
    # Invalid salary range
    invalid_data = {
        "keywords": ["Python"],
        "salary_min": 100000,
        "salary_max": 50000
    }
    response = client.post("/api/preferences", json=invalid_data, headers=auth_headers)
    assert response.status_code == 422


def test_preferences_require_auth(client: TestClient):
    """Test that preferences endpoints require authentication"""
    response = client.get("/api/preferences")
    assert response.status_code == 403