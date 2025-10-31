import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class SourceTypeEnum(str, enum.Enum):
    """Source type enumeration"""
    RSS = "rss"
    API = "api"
    SCRAPER = "scraper"


class LogLevelEnum(str, enum.Enum):
    """Log level enumeration"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    preferences: Mapped[list["UserPreference"]] = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    verification_tokens: Mapped[list["VerificationToken"]] = relationship("VerificationToken", back_populates="user", cascade="all, delete-orphan")


class JobSource(Base):
    __tablename__ = "job_sources"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[SourceTypeEnum] = mapped_column(Enum(SourceTypeEnum), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # 1-10, higher = more important
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scrape_frequency: Mapped[int] = mapped_column(Integer, default=7200, nullable=False)  # seconds, default 2 hours
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Statistics
    total_jobs_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[Optional[float]] = mapped_column(nullable=True)  # Calculated field
    
    # Relationships
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="source", cascade="all, delete-orphan")
    scraper_logs: Mapped[list["ScraperLog"]] = relationship("ScraperLog", back_populates="source", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    company: Mapped[Optional[str]] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    remote_work: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    job_type: Mapped[Optional[str]] = mapped_column(String(100))  # full-time, part-time, contract, etc.
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)  # NEW: Quality score 0.0-1.0
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    source: Mapped["JobSource"] = relationship("JobSource", back_populates="jobs")
    job_metadata: Mapped[list["JobMetadata"]] = relationship("JobMetadata", back_populates="job", cascade="all, delete-orphan")
    
    # Indexes defined at class level
    __table_args__ = (
        Index('ix_jobs_source_posted', 'source_id', 'posted_at'),
        Index('ix_jobs_active_created', 'is_active', 'created_at'),
        Index('ix_jobs_title_company', 'title', 'company'),  # For fuzzy matching
        Index('ix_jobs_quality_score', 'quality_score'),  # NEW: Index for quality filtering
    )


class JobMetadata(Base):
    __tablename__ = "job_metadata"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="job_metadata")
    
    __table_args__ = (
        Index('ix_job_metadata_job_key', 'job_id', 'key'),
    )


class ScraperLog(Base):
    __tablename__ = "scraper_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[LogLevelEnum] = mapped_column(Enum(LogLevelEnum), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)  # FIX: Rename to extra_data
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    source: Mapped["JobSource"] = relationship("JobSource", back_populates="scraper_logs")
    
    __table_args__ = (
        Index('ix_scraper_logs_source_created', 'source_id', 'created_at'),
        Index('ix_scraper_logs_level_created', 'level', 'created_at'),
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    keywords: Mapped[Optional[list]] = mapped_column(JSON)  # List of required keywords
    excluded_keywords: Mapped[Optional[list]] = mapped_column(JSON)  # List of excluded keywords
    location: Mapped[Optional[str]] = mapped_column(String(255))
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    remote_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    job_types: Mapped[Optional[list]] = mapped_column(JSON)  # ["full-time", "part-time", "contract"]
    notification_frequency: Mapped[str] = mapped_column(String(50), default="daily", nullable=False)  # "realtime", "daily", "weekly"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="preferences")
    
    __table_args__ = (
        Index('ix_user_preferences_user_id', 'user_id'),
    )


class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="verification_tokens")