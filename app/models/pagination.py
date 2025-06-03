from typing import List, Generic, TypeVar, Dict, Any, Optional
from pydantic import BaseModel, Field

T = TypeVar('T')

class PaginationMetadata(BaseModel):
    """Metadata for paginated responses"""
    total_count: int = Field(..., description="Total number of records in the database")
    filtered_count: int = Field(..., description="Number of records after applying filters")
    limit: int = Field(..., description="Maximum number of records returned per page")
    offset: int = Field(..., description="Number of records skipped")
    has_more: bool = Field(..., description="Whether there are more records after this page")
    current_page: int = Field(..., description="Current page number")
    total_pages: int = Field(..., description="Total number of pages available")
    filters_applied: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Dictionary of filters that were applied to the query"
    )
    
    class Config:
        schema_extra = {
            "example": {
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

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper with metadata"""
    items: List[T]
    metadata: PaginationMetadata
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    # Example items will depend on the type T
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