"""
Pydantic schemas for user preferences
"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import uuid


class PreferenceBase(BaseModel):
    """Base preference schema"""
    keywords: Optional[List[str]] = Field(None, description="Required keywords to match")
    excluded_keywords: Optional[List[str]] = Field(None, description="Keywords to exclude")
    location: Optional[str] = Field(None, max_length=255, description="Preferred location")
    salary_min: Optional[int] = Field(None, ge=0, description="Minimum salary")
    salary_max: Optional[int] = Field(None, ge=0, description="Maximum salary")
    remote_only: bool = Field(False, description="Only show remote jobs")
    job_types: Optional[List[str]] = Field(None, description="Job types: full-time, part-time, contract")
    notification_frequency: str = Field("daily", description="Notification frequency: realtime, daily, weekly")
    
    @field_validator('keywords')
    @classmethod
    def validate_keywords(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("At least one keyword is required if keywords are provided")
        return v
    
    @field_validator('salary_min', 'salary_max')
    @classmethod
    def validate_salary(cls, v):
        if v is not None and v < 0:
            raise ValueError("Salary must be non-negative")
        return v
    
    @field_validator('notification_frequency')
    @classmethod
    def validate_notification_frequency(cls, v):
        if v not in ['realtime', 'daily', 'weekly', 'none']:
            raise ValueError("Notification frequency must be 'realtime', 'daily', 'weekly', or 'none'")
        return v
    
    @field_validator('job_types')
    @classmethod
    def validate_job_types(cls, v):
        if v is not None:
            valid_types = ['full-time', 'part-time', 'contract', 'freelance', 'internship']
            for job_type in v:
                if job_type not in valid_types:
                    raise ValueError(f"Invalid job type: {job_type}. Must be one of {valid_types}")
        return v


class PreferenceCreate(PreferenceBase):
    """Schema for creating preferences"""
    keywords: List[str] = Field(..., min_length=1, description="At least one keyword required")
    
    @field_validator('salary_min', 'salary_max')
    @classmethod
    def validate_salary_range(cls, v, info):
        # Check if salary_min < salary_max
        if info.field_name == 'salary_max' and 'salary_min' in info.data:
            salary_min = info.data.get('salary_min')
            if salary_min is not None and v is not None and v < salary_min:
                raise ValueError("salary_max must be greater than salary_min")
        return v


class PreferenceUpdate(PreferenceBase):
    """Schema for updating preferences (all fields optional)"""
    pass


class PreferenceOut(PreferenceBase):
    """Schema for preference response"""
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EmailFrequencyUpdate(BaseModel):
    """Schema for updating email notification frequency"""
    notification_frequency: str = Field(..., description="Email frequency: realtime, daily, weekly, or none")
    
    @field_validator('notification_frequency')
    @classmethod
    def validate_frequency(cls, v):
        if v not in ['realtime', 'daily', 'weekly', 'none']:
            raise ValueError("Notification frequency must be 'realtime', 'daily', 'weekly', or 'none'")
        return v