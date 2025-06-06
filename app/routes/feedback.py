from fastapi import APIRouter, HTTPException, status, Query, Body, Header, Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import json
from datetime import datetime
import os
from pathlib import Path
from collections import Counter

from app.models.feedback import (
    Feedback, FeedbackCreate, FeedbackUpdate, FeedbackType, 
    FeedbackStatus, FeedbackBulkImport, PaginatedResponse
)

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"]
)

# Helper functions for DRY principles
def get_current_timestamp() -> datetime:
    """Generate current timestamp in ISO format"""
    return datetime.now()

def validate_enum_value(enum_class, value):
    """Validate that a value is a valid enum member"""
    if value is not None and value not in [e.value for e in enum_class]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid value. Must be one of: {[e.value for e in enum_class]}"
        )
    return value

# Path to feedback data file
DATA_FILE = Path("app/data/feedback.json")

def load_feedback_data() -> List[dict]:
    """Load feedback data from JSON file"""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_feedback_data(data: List[dict]):
    """Save feedback data to JSON file"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def apply_feedback_filters(data: List[dict], **filters) -> List[dict]:
    """Apply multiple filters to feedback data"""
    result = data
    
    # By default, exclude deleted entries unless include_deleted is True
    include_deleted = filters.get('include_deleted', False)
    if not include_deleted:
        result = [f for f in result if not f.get("deleted", False)]
    
    # Type filter
    if filters.get('type'):
        result = [f for f in result if f["type"] == filters['type']]
    
    # Status filter
    if filters.get('status'):
        result = [f for f in result if f["status"] == filters['status']]
    
    # Customer ID filter
    if filters.get('customer_id'):
        result = [f for f in result if f["customer_id"] == str(filters['customer_id'])]
    
    # Date range filters
    if filters.get('created_after'):
        result = [
            f for f in result 
            if datetime.fromisoformat(f["timestamp"]) > filters['created_after']
        ]
    
    if filters.get('created_before'):
        result = [
            f for f in result 
            if datetime.fromisoformat(f["timestamp"]) < filters['created_before']
        ]
    
    return result

def add_admin_note(feedback: dict, note_text: str, author: str = "system") -> dict:
    """
    Add an admin note to a feedback entry
    
    This is designed to be reusable and can be expanded into a more 
    comprehensive activity log or thread system in the future.
    
    Args:
        feedback: The feedback entry dictionary
        note_text: The text content of the admin note
        author: The author of the note (default: "system")
        
    Returns:
        The updated feedback dictionary with the new note appended
    """
    # Initialize admin_notes array if it doesn't exist
    if "admin_notes" not in feedback:
        feedback["admin_notes"] = []
    
    # Create new admin note
    new_note = {
        "text": note_text,
        "author": author,
        "timestamp": get_current_timestamp().isoformat()
    }
    
    # Append to the admin_notes array
    feedback["admin_notes"].append(new_note)
    
    return feedback

def filter_fields(items: List[Dict], fields: Optional[str] = None) -> List[Dict]:
    """
    Filter the items to include only the requested fields
    
    Args:
        items: List of dictionary items
        fields: Comma-separated list of fields to include
        
    Returns:
        List of filtered dictionaries
    """
    if not fields:
        return items
    
    selected_fields = [field.strip() for field in fields.split(',')]
    filtered_items = []
    
    for item in items:
        # Include only the requested fields
        filtered_item = {field: item.get(field) for field in selected_fields if field in item}
        # Always include id for reference
        if 'id' not in filtered_item and 'id' in item:
            filtered_item['id'] = item['id']
        filtered_items.append(filtered_item)
        
    return filtered_items

def log_admin_operation(operation: str, resource: str, details: Dict[str, Any]):
    """
    Log administrative operations for audit purposes
    
    Args:
        operation: The type of operation (e.g., "import", "delete")
        resource: The resource affected (e.g., "feedback")
        details: Operation details including count, user, etc.
    """
    # In a real system, this would write to a secure audit log
    # For this example, we'll just print to console
    log_entry = {
        "timestamp": get_current_timestamp().isoformat(),
        "operation": operation,
        "resource": resource,
        "details": details
    }
    
    print(f"ADMIN OPERATION: {log_entry}")
    # In production, you would log to a secure audit trail
    # log_to_admin_audit_trail(log_entry)


@router.get("", response_model=PaginatedResponse)
async def get_all_feedback(
    type: Optional[str] = Query(None, description="Filter by feedback type (complaint or suggestion)"),
    status: Optional[str] = Query(None, description="Filter by feedback status (open, pending, or resolved)"),
    customer_id: Optional[UUID] = Query(None, description="Filter by exact customer ID match"),
    created_after: Optional[datetime] = Query(None, description="Filter feedback created after this timestamp"),
    created_before: Optional[datetime] = Query(None, description="Filter feedback created before this timestamp"),
    include_deleted: bool = Query(False, description="Include soft-deleted feedback entries"),
    limit: int = Query(10, description="Number of items to return", ge=1, le=100),
    offset: int = Query(0, description="Number of items to skip", ge=0),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to include in response"),
    sort_by: str = Query("timestamp", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)")
):
    """
    Get all feedback entries with advanced filtering, pagination, field selection, and sorting
    
    This endpoint supports comprehensive query capabilities for the feedback dashboard.
    """
    feedback_data = load_feedback_data()
    
    # Validate enum values if provided
    if type is not None:
        validate_enum_value(FeedbackType, type)
    if status is not None:
        validate_enum_value(FeedbackStatus, status)
    
    # Validate sort_order
    if sort_order not in ["asc", "desc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_order must be 'asc' or 'desc'"
        )
    
    # Apply filters
    filtered_data = apply_feedback_filters(
        feedback_data,
        type=type,
        status=status,
        customer_id=customer_id,
        created_after=created_after,
        created_before=created_before,
        include_deleted=include_deleted
    )
    
    # Apply sorting
    try:
        if sort_by == "timestamp":
            # Special handling for timestamp to ensure datetime comparison
            filtered_data.sort(
                key=lambda x: datetime.fromisoformat(x.get(sort_by, "")), 
                reverse=(sort_order == "desc")
            )
        else:
            filtered_data.sort(
                key=lambda x: x.get(sort_by, ""), 
                reverse=(sort_order == "desc")
            )
    except (KeyError, TypeError) as e:
        # If sort_by field doesn't exist or causes an error, use default sorting
        filtered_data.sort(
            key=lambda x: datetime.fromisoformat(x.get("timestamp", "")),
            reverse=True  # Default to newest first
        )
    
    # Get total count before pagination
    total_count = len(filtered_data)
    
    # Apply pagination
    paginated_data = filtered_data[offset:offset + limit]
    
    # Apply field selection
    filtered_items = filter_fields(paginated_data, fields)
    
    # Prepare the paginated response
    response = {
        "items": filtered_items,
        "total_count": total_count,
        "limit": limit,
        "offset": offset
    }
    
    return response
@router.get("/summary", response_model=Dict)
async def get_feedback_summary(
    include_deleted: bool = Query(False, description="Include soft-deleted feedback in the statistics"),
    customer_id: Optional[UUID] = Query(None, description="Filter by exact customer ID"),
    created_after: Optional[datetime] = Query(None, description="Only include feedback created after this timestamp"),
    created_before: Optional[datetime] = Query(None, description="Only include feedback created before this timestamp"),
    include_trends: bool = Query(False, description="Include monthly trend data for the past 6 months")
):
    """
    Get aggregated statistics about feedback entries
    
    Returns counts grouped by type and status for dashboard reporting.
    Can optionally include trend data for the past 6 months.
    By default, deleted entries are excluded from the statistics.
    """
    feedback_data = load_feedback_data()
    
    # Apply filters to get the dataset for statistics
    filtered_data = apply_feedback_filters(
        feedback_data,
        customer_id=customer_id,
        created_after=created_after,
        created_before=created_before,
        include_deleted=include_deleted
    )
    
    # Calculate base statistics
    total_count = len(filtered_data)
    
    # Count by type
    type_counter = Counter()
    for feedback in filtered_data:
        type_counter[feedback["type"]] += 1
    
    # Count by status
    status_counter = Counter()
    for feedback in filtered_data:
        status_counter[feedback["status"]] += 1
    
    # Prepare basic response
    summary = {
        "total": total_count,
        "by_type": dict(type_counter),
        "by_status": dict(status_counter)
    }
    
    # Add trend data if requested
    if include_trends:
        # Get the current date for reference
        now = datetime.now()
        
        # Initialize counters for the last 6 months
        monthly_trends = {}
        
        for feedback in filtered_data:
            # Parse the timestamp
            feedback_date = datetime.fromisoformat(feedback["timestamp"])
            
            # Create a month key in the format "YYYY-MM"
            month_key = f"{feedback_date.year}-{feedback_date.month:02d}"
            
            # Initialize the month in the trends if not present
            if month_key not in monthly_trends:
                monthly_trends[month_key] = {
                    "total": 0,
                    "by_type": {"complaint": 0, "suggestion": 0},
                    "by_status": {"open": 0, "pending": 0, "resolved": 0}
                }
            
            # Increment counters
            monthly_trends[month_key]["total"] += 1
            monthly_trends[month_key]["by_type"][feedback["type"]] += 1
            monthly_trends[month_key]["by_status"][feedback["status"]] += 1
        
        # Add to the summary
        summary["monthly_trends"] = monthly_trends
    
    # Add resolution rate if we have resolved feedback
    if status_counter.get("resolved", 0) > 0:
        resolution_rate = status_counter.get("resolved", 0) / total_count if total_count > 0 else 0
        summary["resolution_rate"] = round(resolution_rate * 100, 2)  # As percentage with 2 decimal places
    
    return summary

@router.post("/import", response_model=List[Feedback], status_code=status.HTTP_201_CREATED)
async def import_feedback(
    import_data: FeedbackBulkImport,
    api_key: str = Header(..., description="Admin API key required for this endpoint")
):
    """
    Bulk import feedback entries (INTERNAL/ADMIN USE ONLY)
    
    This endpoint allows importing multiple feedback entries at once from a legacy system 
    or during data migration.
    
    Security:
    - Requires admin API key authentication
    - Limited to internal operations only
    
    Behavior:
    - All entries must be valid (correct enums, required fields)
    - Each entry will be assigned a server-generated UUID and timestamp
    - If any entry is invalid, the entire operation is rejected (transactional)
    
    WARNING: This endpoint is for internal administrative use only.
    """
    # In a real system, this would validate against a proper auth service
    # For simplicity, we're using a hardcoded value here
    ADMIN_API_KEY = "admin-secret-key-12345"
    
    if api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid admin API key required for this endpoint"
        )
    
    # First validate all entries before inserting any
    for i, item in enumerate(import_data.items):
        try:
            # Validate enum values
            validate_enum_value(FeedbackType, item.type.value)
            validate_enum_value(FeedbackStatus, item.status.value)
        except HTTPException as e:
            # Add item index to error message for easier debugging
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Error in item #{i}: {e.detail}"
            )
    
    # Load existing data
    feedback_data = load_feedback_data()
    
    # Create new entries with generated IDs and timestamps
    new_items = []
    
    for item in import_data.items:
        # Generate a unique timestamp for each item
        current_time = get_current_timestamp()
        
        # Convert to Feedback model with generated ID and timestamp
        new_feedback = Feedback(
            id=uuid4(),
            customer_id=item.customer_id,
            type=item.type,
            message=item.message,
            related_booking_id=item.related_booking_id,
            status=item.status,
            timestamp=current_time,
            admin_notes=[]
        )
        
        # Convert to dict and add to list of new items
        new_items.append(new_feedback.dict())
    
    # Add all new items to existing data
    feedback_data.extend(new_items)
    
    # Save updated data
    save_feedback_data(feedback_data)
    
    # Log the admin operation
    log_admin_operation(
        operation="bulk_import", 
        resource="feedback", 
        details={
            "count": len(new_items),
            "types": Counter([item["type"] for item in new_items])
        }
    )
    
    # Return the newly created items
    return new_items

@router.get("/{feedback_id}", response_model=Feedback)
async def get_feedback(feedback_id: UUID, include_deleted: bool = Query(False, description="Include soft-deleted feedback")):
    """Get a specific feedback by ID, with option to include deleted entries"""
    feedback_data = load_feedback_data()
    
    for feedback in feedback_data:
        if feedback["id"] == str(feedback_id):
            # Check if feedback is deleted and if we should include it
            if feedback.get("deleted", False) and not include_deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Feedback with ID {feedback_id} not found or has been deleted"
                )
            return feedback
            
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Feedback with ID {feedback_id} not found"
    )

@router.post("", response_model=Feedback, status_code=status.HTTP_201_CREATED)
async def create_feedback(feedback: FeedbackCreate):
    """Create a new feedback entry"""
    feedback_data = load_feedback_data()
    
    # Validate enum values
    validate_enum_value(FeedbackType, feedback.type.value)
    validate_enum_value(FeedbackStatus, feedback.status.value)
    
    # Generate new feedback with ID and timestamps
    new_feedback = Feedback(
        id=uuid4(),
        customer_id=feedback.customer_id,
        type=feedback.type,
        message=feedback.message,
        related_booking_id=feedback.related_booking_id,
        status=feedback.status,
        timestamp=get_current_timestamp()
    )
    
    # Convert to dict and add to data
    new_feedback_dict = new_feedback.dict()
    feedback_data.append(new_feedback_dict)
    save_feedback_data(feedback_data)
    
    return new_feedback_dict

@router.put("/{feedback_id}", response_model=Feedback)
async def update_feedback(feedback_id: UUID, feedback_update: FeedbackUpdate):
    """
    Update an existing feedback entry
    
    If admin_note is provided, it will be appended to the admin_notes array
    rather than replacing existing notes.
    """
    feedback_data = load_feedback_data()
    
    # Validate enum values if provided
    if feedback_update.type:
        validate_enum_value(FeedbackType, feedback_update.type.value)
    if feedback_update.status:
        validate_enum_value(FeedbackStatus, feedback_update.status.value)
    
    for i, feedback in enumerate(feedback_data):
        if feedback["id"] == str(feedback_id):
            # Check if feedback is soft-deleted
            if feedback.get("deleted", False):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot update deleted feedback. Restore it first."
                )
                
            # Extract admin note if present
            admin_note = feedback_update.admin_note
            
            # Remove admin_note from the update dict to avoid overwriting the admin_notes array
            update_dict = {k: v for k, v in feedback_update.dict().items() 
                          if v is not None and k != "admin_note"}
            
            # Update the feedback with other fields
            feedback_data[i].update(update_dict)
            
            # Add admin note if provided
            if admin_note:
                feedback_data[i] = add_admin_note(feedback_data[i], admin_note)
            
            save_feedback_data(feedback_data)
            return feedback_data[i]
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Feedback with ID {feedback_id} not found"
    )

@router.delete("/purge", status_code=status.HTTP_200_OK)
async def purge_deleted_feedback(
    api_key: str = Header(..., description="Admin API key required for this endpoint"),
    deleted_before: Optional[datetime] = Query(
        None, 
        description="Only purge items deleted before this date (ISO format)"
    )
):
    """
    Permanently remove all soft-deleted feedback entries (INTERNAL/ADMIN USE ONLY)
    
    This endpoint permanently removes all feedback entries that have been soft-deleted
    (marked with deleted=true). This operation cannot be undone.
    
    Security:
    - Requires admin API key authentication
    - Limited to internal operations only
    
    Options:
    - Can be limited to only purge entries deleted before a specific date
    
    Returns:
    - A summary of how many items were purged
    
    WARNING: This endpoint is for internal administrative use only.
    The delete operation is permanent and cannot be reversed.
    """
    # In a real system, this would validate against a proper auth service
    # For simplicity, we're using a hardcoded value here
    ADMIN_API_KEY = "admin-secret-key-12345"
    
    if api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid admin API key required for this endpoint"
        )
    
    # Load existing data
    feedback_data = load_feedback_data()
    
    # Count items before purging
    initial_count = len(feedback_data)
    
    # Filter out deleted entries, considering the deletion date if specified
    if deleted_before:
        purged_feedback_data = []
        purged_ids = []  # Track purged IDs for logging
        
        for item in feedback_data:
            # Keep the item if:
            # 1. It's not deleted, OR
            # 2. It doesn't have a deletion_timestamp, OR
            # 3. It was deleted after the specified date
            if (not item.get("deleted", False) or 
                "deletion_timestamp" not in item or
                datetime.fromisoformat(item["deletion_timestamp"]) >= deleted_before):
                purged_feedback_data.append(item)
            else:
                purged_ids.append(item.get("id"))
    else:
        # If no date specified, purge all deleted entries
        purged_ids = [item.get("id") for item in feedback_data if item.get("deleted", False)]
        purged_feedback_data = [item for item in feedback_data if not item.get("deleted", False)]
    
    # Count items after purging
    final_count = len(purged_feedback_data)
    purged_count = initial_count - final_count
    
    if purged_count > 0:
        # Only save if something was actually purged
        save_feedback_data(purged_feedback_data)
        
        # Log the admin operation
        log_admin_operation(
            operation="purge", 
            resource="feedback", 
            details={
                "purged_count": purged_count,
                "remaining_count": final_count,
                "deleted_before": deleted_before.isoformat() if deleted_before else "all time",
                "purged_ids": purged_ids[:5] + (["..."] if len(purged_ids) > 5 else [])  # Log first 5 IDs
            }
        )
    
    # Return summary
    return {
        "success": True,
        "message": f"Successfully purged {purged_count} deleted feedback entries" +
                  (f" deleted before {deleted_before.isoformat()}" if deleted_before else ""),
        "purged_count": purged_count,
        "remaining_count": final_count
    }

@router.delete("/{feedback_id}", status_code=status.HTTP_200_OK, response_model=Feedback)
async def soft_delete_feedback(feedback_id: UUID):
    """Soft delete a feedback entry by marking it as deleted"""
    feedback_data = load_feedback_data()
    
    for i, feedback in enumerate(feedback_data):
        if feedback["id"] == str(feedback_id):
            # Check if already deleted
            if feedback.get("deleted", False):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feedback with ID {feedback_id} is already deleted"
                )
            
            # Mark as deleted instead of removing and add deletion timestamp
            feedback_data[i]["deleted"] = True
            feedback_data[i]["deletion_timestamp"] = get_current_timestamp().isoformat()
            save_feedback_data(feedback_data)
            return feedback_data[i]
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Feedback with ID {feedback_id} not found"
    )

@router.put("/{feedback_id}/restore", status_code=status.HTTP_200_OK, response_model=Feedback)
async def restore_feedback(feedback_id: UUID):
    """Restore a previously deleted feedback entry"""
    feedback_data = load_feedback_data()
    
    for i, feedback in enumerate(feedback_data):
        if feedback["id"] == str(feedback_id):
            # Check if it's actually deleted
            if not feedback.get("deleted", False):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feedback with ID {feedback_id} is not deleted"
                )
            
            # Restore by marking deleted as false
            feedback_data[i]["deleted"] = False
            save_feedback_data(feedback_data)
            return feedback_data[i]
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Feedback with ID {feedback_id} not found"
    )

@router.post("/{feedback_id}/notes", response_model=Feedback)
async def add_note_to_feedback(
    feedback_id: UUID, 
    note: str = Body(..., embed=True), 
    author: str = Body("system", embed=True)
):
    """
    Add an admin note to a feedback entry without changing other fields
    
    This endpoint allows adding notes independently of other updates
    """
    feedback_data = load_feedback_data()
    
    for i, feedback in enumerate(feedback_data):
        if feedback["id"] == str(feedback_id):
            # Check if feedback is soft-deleted
            if feedback.get("deleted", False):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot add notes to deleted feedback. Restore it first."
                )
                
            # Add the note
            feedback_data[i] = add_admin_note(feedback_data[i], note, author)
            save_feedback_data(feedback_data)
            return feedback_data[i]
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Feedback with ID {feedback_id} not found"
    )