import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator, Field
from uuid import UUID


class JobBase(BaseModel):
    """Base job schema"""
    title: str
    url: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    remote_work: bool = False
    job_type: Optional[str] = None
    posted_at: Optional[datetime] = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is at least 3 characters"""
        if len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters')
        return v.strip()

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v.strip()

    @model_validator(mode='after')
    def validate_salary_range(self):
        """Validate salary_min < salary_max if both present"""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min >= self.salary_max:
                raise ValueError('salary_min must be less than salary_max')
        return self

    @classmethod
    def normalize_title(cls, title: str) -> str:
        """Normalize and clean job title"""
        # Remove extra whitespace
        title = ' '.join(title.split())
        # Remove common prefixes
        title = re.sub(r'^(Job:|Position:|Role:|Hiring:)\s*', '', title, flags=re.IGNORECASE)
        # Remove emoji and special characters
        title = re.sub(r'[^\w\s\-\+\#\(\)\/]', '', title)
        return title.strip()

    def extract_salary_from_text(self, text: str) -> tuple[Optional[int], Optional[int]]:
        """Extract salary range from text"""
        if not text:
            return None, None
        
        # Pattern for salary ranges like "$80k-$120k" or "$80,000 - $120,000"
        pattern = r'\$\s*(\d+)(?:,(\d+))?\s*[kK]?\s*[-–to]\s*\$?\s*(\d+)(?:,(\d+))?\s*[kK]?'
        match = re.search(pattern, text)
        
        if match:
            min_val = int(match.group(1))
            max_val = int(match.group(3))
            
            # Handle 'k' notation
            if 'k' in text.lower() or 'K' in text:
                min_val *= 1000
                max_val *= 1000
            
            return min_val, max_val
        
        return None, None

    def detect_remote_keywords(self) -> bool:
        """Detect if job is remote based on keywords"""
        if not self.description and not self.location:
            return False
        
        text = f"{self.title} {self.description or ''} {self.location or ''}".lower()
        remote_keywords = [
            'remote', 'work from home', 'wfh', 'distributed', 
            'anywhere', 'location independent', 'virtual'
        ]
        
        return any(keyword in text for keyword in remote_keywords)


class JobIn(JobBase):
    """Schema for incoming job data from scrapers"""
    source_name: str

    class Config:
        str_strip_whitespace = True

class JobOut(JobBase):
    """Schema for job response"""
    id: UUID
    quality_score: Optional[float] = None
    source_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class JobMatchOut(JobOut):
    """Schema for matched job response with relevance score"""
    relevance_score: float = Field(..., description="Match relevance score 0.0-1.0")
    match_reasons: dict = Field(..., description="Reasons why this job matched")
    
    class Config:
        from_attributes = True

class JobCreate(JobBase):
    """Schema for creating a job in database"""
    source_id: UUID

    class Config:
        from_attributes = True


class JobUpdate(BaseModel):
    """Schema for updating a job"""
    title: Optional[str] = None
    description: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    remote_work: Optional[bool] = None
    job_type: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        from_attributes = True

class JobSearchParams(BaseModel):
    """Schema for job search parameters"""
    keywords: Optional[str] = Field(None, description="Keywords to search (comma-separated)")
    location: Optional[str] = Field(None, description="Location filter")
    remote: Optional[bool] = Field(None, description="Remote jobs only")
    min_salary: Optional[int] = Field(None, ge=0, description="Minimum salary")
    max_salary: Optional[int] = Field(None, ge=0, description="Maximum salary")
    job_type: Optional[str] = Field(None, description="Job type filter")
    min_quality: Optional[float] = Field(0.6, ge=0.0, le=1.0, description="Minimum quality score")
    limit: int = Field(50, ge=1, le=100, description="Number of results")
    offset: int = Field(0, ge=0, description="Pagination offset")