# app/models/booking.py
from pydantic import BaseModel, validator, Field
from datetime import date, datetime
from typing import Optional, Dict
from enum import Enum
import uuid

class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class BookingBase(BaseModel):
    customer_id: str
    destination: str
    start_date: date
    end_date: date
    
    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    # Add validators for date fields to convert strings to date objects
    @validator('start_date', 'end_date', pre=True)
    def parse_date(cls, value):
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
        raise ValueError(f"Invalid date format: {value}")

class BookingCreate(BookingBase):
    pass

class Booking(BookingBase):
    booking_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: BookingStatus = BookingStatus.PENDING
    created_at: datetime
    updated_at: datetime

    # Add validators for datetime fields to convert strings to datetime objects
    @validator('created_at', 'updated_at', pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, datetime):
            return value
            
        if isinstance(value, str):
            # Try different datetime formats
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
                    
            # Handle ISO format with timezone info
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
                
        raise ValueError(f"Invalid datetime format: {value}")

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class BookingSummary(BaseModel):
    destination: str
    start_date: date
    end_date: date
    status: BookingStatus
    
    class Config:
        orm_mode = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }

class BookingStats(BaseModel):
    total_bookings: int
    bookings_by_status: Dict[str, int]
    average_duration_days: float