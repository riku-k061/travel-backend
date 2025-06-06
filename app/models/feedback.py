from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID, uuid4


class FeedbackType(str, Enum):
    COMPLAINT = "complaint"
    SUGGESTION = "suggestion"


class FeedbackStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    PENDING = "pending"


class AdminNote(BaseModel):
    text: str
    author: str = "system"  # Default author, can be expanded later
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FeedbackBase(BaseModel):
    customer_id: UUID
    type: FeedbackType
    message: str
    related_booking_id: Optional[UUID] = None
    status: FeedbackStatus = FeedbackStatus.OPEN


class FeedbackCreate(FeedbackBase):
    pass


class FeedbackUpdate(BaseModel):
    type: Optional[FeedbackType] = None
    message: Optional[str] = None
    related_booking_id: Optional[UUID] = None
    status: Optional[FeedbackStatus] = None
    admin_note: Optional[str] = None  # Optional field for adding a new admin note


class Feedback(FeedbackBase):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now)
    admin_notes: List[AdminNote] = []
    deleted: bool = False

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }

class FeedbackSummary(BaseModel):
    total: int
    by_type: dict
    by_status: dict

class PaginatedResponse(BaseModel):
    items: List[Dict[str, Any]]
    total_count: int
    limit: int
    offset: int

class FeedbackBulkImport(BaseModel):
    items: List[FeedbackCreate]
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "customer_id": "e9a25dae-5d5d-4a91-8e9d-f21d2ca95af4",
                        "type": "complaint",
                        "message": "Flight was delayed by 3 hours",
                        "related_booking_id": "c29a5e8a-ce47-4fbc-8a5d-48f4b8934851",
                        "status": "open"
                    },
                    {
                        "customer_id": "a7c86c9c-f9b8-4d10-9c9d-3a977c0e30c2",
                        "type": "suggestion",
                        "message": "Consider adding vegetarian meal options",
                        "status": "pending"
                    }
                ]
            }
        }