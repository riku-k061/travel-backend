# app/models/vehicle.py
from typing import List, Optional, Generic, TypeVar, Dict, Any
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

T = TypeVar('T')

class PaginatedResponse(GenericModel, Generic[T]):
    """Generic paginated response model that can wrap any data type"""
    items: List[T]
    total_count: int
    
    class Config:
        schema_extra = {
            "example": {
                "items": [],
                "total_count": 0
            }
        }

class VehicleBase(BaseModel):
    type: str
    capacity: int
    available: bool = True
    destination_ids: List[str] = []

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    type: Optional[str] = None
    capacity: Optional[int] = None
    available: Optional[bool] = None
    destination_ids: Optional[List[str]] = None

class Vehicle(VehicleBase):
    id: str

    class Config:
        schema_extra = {
            "example": {
                "id": "veh-001",
                "type": "bus",
                "capacity": 50,
                "available": True,
                "destination_ids": ["dest-001", "dest-002"]
            }
        }