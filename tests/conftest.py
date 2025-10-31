"""
Pytest configuration and fixtures
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import uuid

from app.main import app
from app.core.database import get_db, Base
from app.models import User, Job, JobSource
from app.core.security import get_password_hash


# Test database URL
TEST_DATABASE_URL = "postgresql://postgres:postgres@db:5432/arbeit_test"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database and tables"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client"""
    def override_get_db():
        return test_db
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db):
    """Create a test user"""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Get authentication headers for test user"""
    from app.core.security import create_access_token
    token = create_access_token({"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_source(test_db):
    """Create a test job source"""
    source = JobSource(
        id=uuid.uuid4(),
        name="TestSource",
        url="https://test.com/jobs",
        source_type="rss",
        is_active=True,
        priority=5
    )
    test_db.add(source)
    test_db.commit()
    test_db.refresh(source)
    return source


@pytest.fixture
def sample_jobs(test_db, test_source):
    """Create sample jobs for testing"""
    jobs = [
        Job(
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
            source_id=test_source.id,
            posted_at=datetime.utcnow(),
            is_active=True
        ),
        Job(
            id=uuid.uuid4(),
            title="Remote Python Engineer",
            url="https://example.com/job/2",
            company="Remote Co",
            location="Remote",
            description="Python and Django development for remote team.",
            salary_min=70000,
            salary_max=90000,
            remote_work=True,
            job_type="full-time",
            quality_score=0.85,
            source_id=test_source.id,
            posted_at=datetime.utcnow() - timedelta(days=2),
            is_active=True
        ),
        Job(
            id=uuid.uuid4(),
            title="Java Developer",
            url="https://example.com/job/3",
            company="Enterprise Inc",
            location="Munich, Germany",
            description="Looking for Java Spring developers.",
            salary_min=55000,
            salary_max=75000,
            remote_work=False,
            job_type="full-time",
            quality_score=0.8,
            source_id=test_source.id,
            posted_at=datetime.utcnow() - timedelta(days=5),
            is_active=True
        ),
        Job(
            id=uuid.uuid4(),
            title="Frontend Developer React",
            url="https://example.com/job/4",
            company="Startup GmbH",
            location="Berlin, Germany",
            description="React and TypeScript frontend development.",
            salary_min=50000,
            salary_max=70000,
            remote_work=True,
            job_type="full-time",
            quality_score=0.75,
            source_id=test_source.id,
            posted_at=datetime.utcnow() - timedelta(days=1),
            is_active=True
        ),
        Job(
            id=uuid.uuid4(),
            title="DevOps Engineer",
            url="https://example.com/job/5",
            company="Cloud Services",
            location="Remote",
            description="AWS and Kubernetes experience required.",
            salary_min=65000,
            salary_max=85000,
            remote_work=True,
            job_type="full-time",
            quality_score=0.88,
            source_id=test_source.id,
            posted_at=datetime.utcnow() - timedelta(days=3),
            is_active=True
        )
    ]
    
    for job in jobs:
        test_db.add(job)
    test_db.commit()
    
    for job in jobs:
        test_db.refresh(job)
    
    return jobs