# app/models/staff.py
from typing import List, Optional, Dict
from pydantic import BaseModel, EmailStr, Field
from uuid import uuid4

class StaffBase(BaseModel):
    name: str
    role: str
    contact_email: EmailStr
    available: bool = True
    destination_ids: Optional[List[str]] = None

class StaffCreate(StaffBase):
    pass

class StaffUpdate(StaffBase):
    name: Optional[str] = None
    role: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    available: Optional[bool] = None

class StaffInDB(StaffBase):
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    class Config:
        from_attributes = True

class Staff(StaffInDB):
    pass

class PaginatedStaffResponse(BaseModel):
    """Model for paginated staff response"""
    items: List[Staff]
    total_count: int

class RoleSummary(BaseModel):
    """Summary of staff counts by availability status for a specific role"""
    total: int
    available: int
    unavailable: int

class StaffSummary(BaseModel):
    """Overall summary of staff counts with breakdown by role"""
    total_staff: int
    by_role: Dict[str, RoleSummary]