from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional
from datetime import datetime
import uuid
import json

class ScheduleBase(BaseModel):
    destination_id: str
    date: datetime
    capacity: int = Field(gt=0)  # Ensure capacity is greater than 0
    status: str = "active"  # Default status is active

    @validator('date')
    def validate_date_format(cls, v):
        # This validator ensures the date is properly formatted when model is created
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Invalid date format. Please use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)')
        return v

    class Config:
        json_encoders = {
            # Custom encoder for ISO 8601 formatting with Z suffix
            datetime: lambda v: v.isoformat() + "Z" if v.tzinfo else v.isoformat() + "Z"
        }

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleUpdate(BaseModel):
    destination_id: Optional[str] = None
    date: Optional[datetime] = None
    capacity: Optional[int] = Field(default=None, gt=0)
    status: Optional[str] = None  # Allow status updates

    @validator('date')
    def validate_date_format(cls, v):
        # Same validation logic as in ScheduleBase
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Invalid date format. Please use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)')
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z" if v.tzinfo else v.isoformat() + "Z"
        }

class Schedule(ScheduleBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "destination_id": "789e4567-e89b-12d3-a456-426614174001",
                "date": "2023-06-15T10:00:00Z",
                "capacity": 30,
                "status": "active"
            }
        }
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z" if v.tzinfo else v.isoformat() + "Z"
        }

# Custom JSON encoder for dates in app/routes/schedules.py
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat() + "Z"
        return super(DateTimeEncoder, self).default(obj)
    
class StatusSummary(BaseModel):
    status_counts: Dict[str, int]
    total: int

