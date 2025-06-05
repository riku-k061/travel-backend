# app/routes/staff.py
from fastapi import APIRouter, HTTPException, status, Query, Body, Path
from typing import List, Optional, Dict
from collections import defaultdict
import json
import os
from uuid import uuid4

from app.models.staff import Staff, StaffCreate, StaffUpdate, PaginatedStaffResponse, StaffSummary, RoleSummary

router = APIRouter(
    prefix="/staff",
    tags=["staff"],
    responses={404: {"description": "Not found"}},
)

# Paths to data files
STAFF_DATA_FILE = os.path.join(os.path.dirname(__file__), "../data/staff.json")
DESTINATION_DATA_FILE = os.path.join(os.path.dirname(__file__), "../data/destinations.json")

# Helper function to read staff data
def read_staff_data():
    try:
        with open(STAFF_DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return empty list if file doesn't exist or is invalid
        return []

# Helper function to write staff data
def write_staff_data(data):
    os.makedirs(os.path.dirname(STAFF_DATA_FILE), exist_ok=True)
    with open(STAFF_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Helper function to read destination data
def read_destination_data():
    try:
        with open(DESTINATION_DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return empty list if file doesn't exist or is invalid
        return []

# Helper function to validate destination IDs
def validate_guide_destinations(role, destination_ids):
    # If role contains "guide" (case insensitive)
    if role and "guide" in role.lower():
        # Check if destination_ids is provided and not empty
        if not destination_ids or len(destination_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff with 'guide' role must have at least one destination ID"
            )
        
        # Validate that the destination IDs exist in the destinations.json file
        valid_destination_ids = [dest["destination_id"] for dest in read_destination_data()]
        
        for dest_id in destination_ids:
            if dest_id not in valid_destination_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Destination ID '{dest_id}' does not exist"
                )

# Helper function to validate email uniqueness
def validate_unique_email(email, exclude_staff_id=None):
    """
    Validate that the email is unique among staff members.
    
    Parameters:
    - email: The email to validate
    - exclude_staff_id: Optional staff ID to exclude from the check (for updates)
    
    Raises HTTPException if the email is already in use by another staff member.
    """
    staff_data = read_staff_data()
    
    for staff in staff_data:
        # Skip the current staff member when updating
        if exclude_staff_id and staff["id"] == exclude_staff_id:
            continue
            
        if staff["contact_email"].lower() == email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another staff member"
            )

@router.get("/", response_model=PaginatedStaffResponse)
async def get_all_staff(
    role: Optional[str] = None,
    available: Optional[bool] = None,
    limit: int = Query(10, ge=1, le=100, description="Number of staff members to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of staff members to skip")
):
    """
    Retrieve staff members with optional filtering and pagination.
    
    Parameters:
    - role: Filter staff by role (e.g., "Guide", "Administrative Staff")
    - available: Filter staff by availability status (true/false)
    - limit: Maximum number of staff members to return (default: 10, max: 100)
    - offset: Number of staff members to skip (default: 0)
    
    Returns:
    - Paginated list of staff members and total count
    """
    staff_data = read_staff_data()
    
    # Apply filters if provided
    filtered_staff = staff_data
    
    # Filter by role if role parameter is provided
    if role is not None:
        # Case-insensitive partial match for role
        filtered_staff = [
            staff for staff in filtered_staff 
            if role.lower() in staff["role"].lower()
        ]
    
    # Filter by availability if available parameter is provided
    if available is not None:
        filtered_staff = [
            staff for staff in filtered_staff 
            if staff["available"] == available
        ]
    
    # Store the total count before pagination
    total_count = len(filtered_staff)
    
    # Apply pagination
    paginated_staff = filtered_staff[offset:offset + limit]
    
    # Return paginated response
    return {
        "items": paginated_staff,
        "total_count": total_count
    }

@router.get("/summary", response_model=StaffSummary)
async def get_staff_summary():
    """
    Get a summary of staff counts with breakdown by role and availability status.
    
    Returns:
    - Total count of all staff members
    - Breakdown of staff counts by role and availability status
    """
    staff_data = read_staff_data()
    
    # Initialize counters
    total_staff = len(staff_data)
    role_counters = defaultdict(lambda: {"total": 0, "available": 0, "unavailable": 0})
    
    # Process each staff member
    for staff in staff_data:
        # Normalize role for consistency
        role = staff["role"].lower()
        
        # Update counters
        role_counters[role]["total"] += 1
        
        if staff["available"]:
            role_counters[role]["available"] += 1
        else:
            role_counters[role]["unavailable"] += 1
    
    # Convert defaultdict to regular dict for the response
    role_summary = {}
    for role, counts in role_counters.items():
        role_summary[role] = RoleSummary(
            total=counts["total"],
            available=counts["available"],
            unavailable=counts["unavailable"]
        )
    
    # Return the summary
    return StaffSummary(
        total_staff=total_staff,
        by_role=role_summary
    )

@router.get("/{staff_id}", response_model=Staff)
async def get_staff_by_id(staff_id: str):
    """
    Retrieve a staff member by ID.
    """
    staff_data = read_staff_data()
    for staff in staff_data:
        if staff["id"] == staff_id:
            return staff
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Staff member with ID {staff_id} not found"
    )

@router.post("/", response_model=Staff, status_code=status.HTTP_201_CREATED)
async def create_staff(staff: StaffCreate = Body(...)):
    """
    Create a new staff member.
    
    Validation rules:
    - If role contains 'guide', destination_ids must be provided and non-empty
    - All destination_ids must be valid and exist in the system
    - contact_email must be unique across all staff members
    """
    # Convert to dict for easier manipulation
    new_staff = staff.dict()
    
    # Validate destination IDs for guide roles
    validate_guide_destinations(new_staff.get("role"), new_staff.get("destination_ids"))
    
    # Validate that the email is unique
    validate_unique_email(new_staff["contact_email"])
    
    # Add ID for new staff
    new_staff["id"] = str(uuid4())
    
    # Save to database
    staff_data = read_staff_data()
    staff_data.append(new_staff)
    write_staff_data(staff_data)
    
    return new_staff

@router.put("/{staff_id}", response_model=Staff)
async def update_staff(staff_id: str, staff_update: StaffUpdate = Body(...)):
    """
    Update a staff member by ID.
    
    Validation rules:
    - If role is updated to 'guide', destination_ids must be provided and non-empty
    - All destination_ids must be valid and exist in the system
    - If contact_email is updated, it must be unique across all staff members
      (except for the current staff member being updated)
    """
    staff_data = read_staff_data()
    
    # Find the staff member to update
    staff_index = None
    for i, staff in enumerate(staff_data):
        if staff["id"] == staff_id:
            staff_index = i
            break
    
    if staff_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {staff_id} not found"
        )
    
    # Get update data with non-None values
    update_data = {k: v for k, v in staff_update.dict().items() if v is not None}
    
    # Check if we're updating role or destination_ids
    current_role = staff_data[staff_index].get("role")
    new_role = update_data.get("role", current_role)
    
    # If destination_ids is not in the update, use the existing ones
    if "destination_ids" not in update_data:
        current_destination_ids = staff_data[staff_index].get("destination_ids")
        # Handle the case where existing destination_ids might be None
        if current_destination_ids is None and "guide" in new_role.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff with 'guide' role must have at least one destination ID"
            )
        update_data["destination_ids"] = current_destination_ids
    
    # Validate destination IDs for guide roles
    validate_guide_destinations(new_role, update_data.get("destination_ids"))
    
    # If contact_email is being updated, validate uniqueness
    if "contact_email" in update_data:
        validate_unique_email(update_data["contact_email"], exclude_staff_id=staff_id)
    
    # Apply the update
    staff_data[staff_index].update(update_data)
    write_staff_data(staff_data)
    
    return staff_data[staff_index]

@router.delete("/{staff_id}", status_code=status.HTTP_200_OK, response_model=Staff)
async def deactivate_staff(staff_id: str):
    """
    Deactivate a staff member by ID (set available=false).
    """
    staff_data = read_staff_data()
    
    for i, staff in enumerate(staff_data):
        if staff["id"] == staff_id:
            # Mark the staff member as unavailable instead of removing
            staff_data[i]["available"] = False
            write_staff_data(staff_data)
            return staff_data[i]
            
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Staff member with ID {staff_id} not found"
    )

@router.put("/{staff_id}/reactivate", status_code=status.HTTP_200_OK, response_model=Staff)
async def reactivate_staff(staff_id: str):
    """
    Reactivate a previously deactivated staff member (set available=true).
    """
    staff_data = read_staff_data()
    
    for i, staff in enumerate(staff_data):
        if staff["id"] == staff_id:
            # Reactivate the staff member
            staff_data[i]["available"] = True
            write_staff_data(staff_data)
            return staff_data[i]
            
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Staff member with ID {staff_id} not found"
    )

@router.get("/assigned-to/{destination_id}", response_model=List[Staff])
async def get_guides_by_destination(
    destination_id: str = Path(..., description="ID of the destination to find guides for"),
    available: Optional[bool] = Query(None, description="Filter guides by availability status")
):
    """
    Retrieve all guides assigned to a specific destination.
    
    Parameters:
    - destination_id: ID of the destination to find guides for
    - available: Optional filter for guide availability status
    
    Returns:
    - List of staff members whose role includes 'guide' and have the specified destination 
      in their destination_ids list
    """
    # Validate that the destination exists
    destination_data = read_destination_data()
    destination_exists = any(dest["destination_id"] == destination_id for dest in destination_data)
    
    if not destination_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination with ID {destination_id} not found"
        )
    
    # Get all staff data
    staff_data = read_staff_data()
    
    # Filter for guides assigned to the specific destination
    assigned_guides = [
        staff for staff in staff_data
        if (
            # Check if role includes "guide"
            "guide" in staff["role"].lower() and
            # Check if destination_ids list contains the specified destination_id
            staff.get("destination_ids") and
            destination_id in staff["destination_ids"] and
            # Apply availability filter if provided
            (available is None or staff["available"] == available)
        )
    ]
    
    return assigned_guides
