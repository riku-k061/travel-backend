# app/routes/schedules.py
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
import json
import os
from datetime import datetime, timezone
from collections import Counter
import uuid

from app.models.schedule import Schedule, ScheduleCreate, ScheduleUpdate, StatusSummary, DateTimeEncoder

router = APIRouter(
    prefix="/schedules",
    tags=["schedules"]
)

# Paths to JSON data files
SCHEDULES_FILE = "app/data/schedules.json"
DESTINATIONS_FILE = "app/data/destinations.json"

# Helper function to load schedules data
def load_schedules():
    if not os.path.exists(SCHEDULES_FILE):
        return []
    with open(SCHEDULES_FILE, "r") as f:
        return json.load(f)

# Updated helper function to save schedules data
def save_schedules(schedules):
    with open(SCHEDULES_FILE, "w") as f:
        json.dump(schedules, f, indent=2, cls=DateTimeEncoder)

# Improved function to handle date parsing
def parse_iso_date(date_str):
    """Parse an ISO 8601 date string to offset-aware datetime."""
    if not date_str:
        return None
    try:
        if date_str.endswith("Z"):
            date_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            # Force UTC if tzinfo is missing
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: '{date_str}'. Please use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)"
        )
# Helper function to check if destination exists
def destination_exists(destination_id):
    if not os.path.exists(DESTINATIONS_FILE):
        return False
    
    with open(DESTINATIONS_FILE, "r") as f:
        destinations = json.load(f)
    
    for destination in destinations:
        if destination.get("destination_id") == destination_id:
            return True
    
    return False

@router.get("/status-summary", response_model=StatusSummary, tags=["analytics"])
async def get_schedule_status_summary():
    """
    Returns a summary count of schedules grouped by status (active, inactive, archived).
    Useful for dashboard analytics and administrative overviews.
    """
    schedules = load_schedules()
    
    # Initialize counter with all possible statuses (to ensure they appear in response even if count is 0)
    valid_statuses = ["active", "inactive", "archived"]
    status_counts = {status: 0 for status in valid_statuses}
    
    # Count schedules by status
    for schedule in schedules:
        status = schedule.get("status", "active")  # Default to 'active' if not specified
        
        # Only count valid statuses
        if status in valid_statuses:
            status_counts[status] += 1
        else:
            # For any invalid status values in the data, count them as "unknown"
            if "unknown" not in status_counts:
                status_counts["unknown"] = 0
            status_counts["unknown"] += 1
    
    # Calculate total count
    total_count = sum(status_counts.values())
    
    return StatusSummary(
        status_counts=status_counts,
        total=total_count
    )

# GET all schedules
@router.get("/", response_model=List[Schedule])
async def get_all_schedules(
    destination_id: Optional[str] = None,
    start_date: Optional[str] = None,  # Changed to string for better error handling
    end_date: Optional[str] = None,    # Changed to string for better error handling
    sort: Optional[str] = "asc"        # Default sorting is ascending
):
    schedules = load_schedules()
    
    # Filter by destination_id if provided
    if destination_id:
        schedules = [s for s in schedules if s.get("destination_id") == destination_id]
    
    # Parse date filters
    start_datetime = parse_iso_date(start_date) if start_date else None
    end_datetime = parse_iso_date(end_date) if end_date else None
    
    # Convert all schedule dates to datetime objects
    for schedule in schedules:
        if isinstance(schedule.get("date"), str):
            try:
                schedule["date"] = parse_iso_date(schedule["date"])
            except HTTPException:
                # If date parsing fails, set to None so it won't match any filters
                schedule["date"] = None
    
    # Filter by date range if provided
    if start_datetime:
        schedules = [s for s in schedules if s.get("date") and s.get("date") >= start_datetime]
    
    if end_datetime:
        schedules = [s for s in schedules if s.get("date") and s.get("date") <= end_datetime]
    
    # Validate sort parameter
    if sort.lower() not in ["asc", "desc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sort parameter must be either 'asc' or 'desc'"
        )
    
    # Sort schedules by date
    reverse_sort = sort.lower() == "desc"
    schedules = sorted(
        schedules, 
        key=lambda x: x.get("date", datetime.max) if x.get("date") else datetime.max,
        reverse=reverse_sort
    )
    
    return schedules

# GET schedule by ID
@router.get("/{schedule_id}", response_model=Schedule)
async def get_schedule(schedule_id: str):
    schedules = load_schedules()
    
    for schedule in schedules:
        if schedule.get("id") == schedule_id:
            # Convert string date to datetime
            if isinstance(schedule.get("date"), str):
                try:
                    schedule["date"] = parse_iso_date(schedule["date"])
                except HTTPException:
                    # For invalid dates, set to a default value or raise an error
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Invalid date format in stored schedule data"
                    )
            
            return schedule
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule with ID {schedule_id} not found")

# POST create new schedule
@router.post("/", response_model=Schedule, status_code=status.HTTP_201_CREATED)
async def create_schedule(schedule: ScheduleCreate):
    # Validate destination exists
    if not destination_exists(schedule.destination_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Destination with ID {schedule.destination_id} does not exist"
        )
    
    # Validate status if provided
    valid_statuses = ["active", "inactive", "archived"]
    if schedule.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status value. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Load existing schedules
    schedules = load_schedules()
    
    # Create new schedule with ID
    new_schedule = Schedule(
        id=str(uuid.uuid4()),
        destination_id=schedule.destination_id,
        date=schedule.date,
        capacity=schedule.capacity,
        status=schedule.status
    )
    
    # Convert to dict for storage
    new_schedule_dict = new_schedule.dict()
    
    # Add to schedules list
    schedules.append(new_schedule_dict)
    
    # Save updated data
    save_schedules(schedules)
    
    return new_schedule

# PUT update schedule
@router.put("/{schedule_id}", response_model=Schedule)
async def update_schedule(schedule_id: str, schedule_update: ScheduleUpdate):
    schedules = load_schedules()
    
    # Find the schedule to update
    for i, schedule in enumerate(schedules):
        if schedule.get("id") == schedule_id:
            # If destination_id is provided, validate it exists
            if schedule_update.destination_id is not None:
                if not destination_exists(schedule_update.destination_id):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Destination with ID {schedule_update.destination_id} does not exist"
                    )
                schedules[i]["destination_id"] = schedule_update.destination_id
            
            # Update other fields if provided
            if schedule_update.date is not None:
                schedules[i]["date"] = schedule_update.date
            
            if schedule_update.capacity is not None:
                schedules[i]["capacity"] = schedule_update.capacity
                
            # Update status if provided
            if schedule_update.status is not None:
                # Validate status value
                valid_statuses = ["active", "inactive", "archived"]
                if schedule_update.status not in valid_statuses:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid status value. Must be one of: {', '.join(valid_statuses)}"
                    )
                schedules[i]["status"] = schedule_update.status
            
            # Save updated schedules
            save_schedules(schedules)
            
            # Return updated schedule
            updated_schedule = schedules[i].copy()
            
            # Convert string date to datetime for response
            if isinstance(updated_schedule.get("date"), str):
                try:
                    updated_schedule["date"] = datetime.fromisoformat(updated_schedule["date"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            
            return updated_schedule
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule with ID {schedule_id} not found")

# DELETE schedule
@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: str):
    schedules = load_schedules()
    
    # Find the schedule to delete
    for i, schedule in enumerate(schedules):
        if schedule.get("id") == schedule_id:
            # Remove the schedule
            del schedules[i]
            
            # Save updated schedules
            save_schedules(schedules)
            
            return
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule with ID {schedule_id} not found")