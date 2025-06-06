from enum import Enum
from datetime import datetime, date
from typing import List, Generic, TypeVar, Dict, Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, condecimal
from app.models.pagination import PaginatedResponse


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "cryptocurrency"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"  # Adding this status
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELED = "canceled"


class PaymentBase(BaseModel):
    booking_id: UUID
    method: PaymentMethod
    amount: condecimal(max_digits=10, decimal_places=2)
    status: PaymentStatus = PaymentStatus.PENDING
    transaction_date: datetime = Field(default_factory=datetime.now)
    

class PaymentCreate(PaymentBase):
    pass


class Payment(PaymentBase):
    id: UUID = Field(default_factory=uuid4)
    
    class Config:
        from_attributes = True

class PaginatedPaymentResponse(PaginatedResponse[Payment]):
    """Paginated response containing payment items and metadata"""
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                        "booking_id": "e7f41c69-ccb2-4a42-a9a5-5ad4aa4b0123",
                        "method": "credit_card",
                        "amount": 1299.99,
                        "status": "completed",
                        "transaction_date": "2023-08-15T14:30:25"
                    }
                ],
                "metadata": {
                    "total_count": 100,
                    "filtered_count": 25,
                    "limit": 10,
                    "offset": 0,
                    "has_more": True,
                    "current_page": 1,
                    "total_pages": 3,
                    "filters_applied": {
                        "status": "completed",
                        "min_amount": 1000
                    }
                }
            }
        }

class PaymentMethodSummary(BaseModel):
    """Summary statistics for a specific payment method"""
    method: str
    count: int
    total_amount: float
    percentage_of_total: float

class PaymentStatusSummary(BaseModel):
    """Summary statistics for a specific payment status"""
    status: str
    count: int
    total_amount: float
    percentage_of_total: float

class PaymentSummary(BaseModel):
    """Summary statistics for payments"""
    # Overall statistics
    total_payments: int = Field(..., description="Total number of payments")
    total_amount: float = Field(..., description="Total amount of all payments")
    average_amount: float = Field(..., description="Average payment amount")
    min_amount: float = Field(..., description="Minimum payment amount")
    max_amount: float = Field(..., description="Maximum payment amount")
    
    # Status breakdown
    confirmed_payments: int = Field(..., description="Number of confirmed payments")
    confirmed_amount: float = Field(..., description="Total amount of confirmed payments")
    completed_payments: int = Field(..., description="Number of completed payments")
    completed_amount: float = Field(..., description="Total amount of completed payments")
    pending_payments: int = Field(..., description="Number of pending payments")
    pending_amount: float = Field(..., description="Total amount of pending payments")
    failed_payments: int = Field(..., description="Number of failed payments")
    failed_amount: float = Field(..., description="Total amount of failed payments")
    
    # Detailed breakdowns
    by_method: List[PaymentMethodSummary] = Field(
        ..., 
        description="Payment statistics broken down by payment method"
    )
    by_status: List[PaymentStatusSummary] = Field(
        ..., 
        description="Payment statistics broken down by payment status"
    )
    
    # Time information
    earliest_payment_date: Optional[datetime] = Field(
        None, 
        description="Date of the earliest payment in the dataset"
    )
    latest_payment_date: Optional[datetime] = Field(
        None, 
        description="Date of the latest payment in the dataset"
    )
    date_range_start: Optional[date] = Field(
        None,
        description="Start of date range filter (if applied)"
    )
    date_range_end: Optional[date] = Field(
        None,
        description="End of date range filter (if applied)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "total_payments": 120,
                "total_amount": 156750.25,
                "average_amount": 1306.25,
                "min_amount": 50.00,
                "max_amount": 5000.00,
                "confirmed_payments": 45,
                "confirmed_amount": 58432.50,
                "completed_payments": 65,
                "completed_amount": 85467.75,
                "pending_payments": 8,
                "pending_amount": 10350.00,
                "failed_payments": 2,
                "failed_amount": 2500.00,
                "by_method": [
                    {
                        "method": "credit_card",
                        "count": 75,
                        "total_amount": 98540.25,
                        "percentage_of_total": 62.5
                    },
                    {
                        "method": "paypal",
                        "count": 30,
                        "total_amount": 39500.00,
                        "percentage_of_total": 25.0
                    }
                ],
                "by_status": [
                    {
                        "status": "completed",
                        "count": 65,
                        "total_amount": 85467.75,
                        "percentage_of_total": 54.17
                    }
                ],
                "earliest_payment_date": "2023-01-15T08:30:00",
                "latest_payment_date": "2023-08-20T17:45:22",
                "date_range_start": "2023-06-01",
                "date_range_end": "2023-08-31"
            }
        }