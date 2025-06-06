# app/routes/bookings.py
import json
import os
from typing import List, Optional
from datetime import datetime
import uuid
from functools import lru_cache
from fastapi import APIRouter, HTTPException, Body, Query, status
from ..models.booking import Booking, BookingCreate, BookingStatus, BookingSummary, BookingStats
from statistics import mean
from collections import Counter

router = APIRouter(
    prefix="/bookings",
    tags=["bookings"],
    responses={404: {"description": "Not found"}},
)

DATA_FILE = "app/data/bookings.json"

@lru_cache(maxsize=1)
def get_bookings_data():
    """
    Load bookings data from JSON file with caching to reduce disk I/O.
    The cache is invalidated whenever bookings are saved.
    """
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump([], f)
        return []
        
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_bookings_data(data):
    """
    Save bookings data to JSON file and invalidate the cache.
    """
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, default=str, indent=4)
    # Invalidate the cache after saving
    get_bookings_data.cache_clear()

@router.post("/", response_model=Booking, status_code=status.HTTP_201_CREATED)
def create_booking(booking: BookingCreate = Body(...)):
    bookings = get_bookings_data()
    
    now = datetime.now().isoformat()
    new_booking = {
        "booking_id": str(uuid.uuid4()),
        "customer_id": booking.customer_id,
        "destination": booking.destination,
        "start_date": str(booking.start_date),
        "end_date": str(booking.end_date),
        "status": BookingStatus.PENDING,
        "created_at": now,
        "updated_at": now
    }
    
    bookings.append(new_booking)
    save_bookings_data(bookings)
    
    return new_booking

@router.get("/", response_model=List[Booking])
def read_bookings():
    return get_bookings_data()

@router.get("/search", response_model=List[Booking])
def search_bookings(
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID")
):
    try:
        bookings = get_bookings_data()
        filtered_bookings = []
        
        # Apply filters to minimize iterations
        for booking in bookings:
            # Skip if status filter is provided and doesn't match
            if status is not None and booking.get("status") != status:
                continue
                
            # Skip if customer_id filter is provided and doesn't match
            if customer_id is not None and booking.get("customer_id") != customer_id:
                continue
                
            # If we made it here, the booking passes all filters
            filtered_bookings.append(booking)
        
        # Sort by created_at in descending order
        def get_created_at(booking):
            try:
                created_at_str = booking.get("created_at")
                if isinstance(created_at_str, str):
                    # Handle different datetime formats
                    if 'T' in created_at_str:
                        # ISO format like "2023-01-10T00:00:00"
                        return datetime.fromisoformat(created_at_str)
                    else:
                        # Simple date like "2023-01-10"
                        return datetime.strptime(created_at_str, "%Y-%m-%d")
                return datetime.min
            except (ValueError, TypeError):
                return datetime.min
        
        filtered_bookings.sort(key=get_created_at, reverse=True)
        
        return filtered_bookings
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching bookings: {str(e)}"
        )

@router.get("/{booking_id}", response_model=Booking)
def read_booking(booking_id: str):
    bookings = get_bookings_data()
    for booking in bookings:
        if booking["booking_id"] == booking_id:
            return booking
    raise HTTPException(status_code=404, detail="Booking not found")

@router.put("/{booking_id}", response_model=Booking)
def update_booking(booking_id: str, booking_update: BookingCreate):
    bookings = get_bookings_data()
    
    for i, booking in enumerate(bookings):
        if booking["booking_id"] == booking_id:
            updated_booking = {
                "booking_id": booking_id,
                "customer_id": booking_update.customer_id,
                "destination": booking_update.destination,
                "start_date": str(booking_update.start_date),
                "end_date": str(booking_update.end_date),
                "status": booking.get("status", BookingStatus.PENDING),
                "created_at": booking.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat()
            }
            bookings[i] = updated_booking
            save_bookings_data(bookings)
            return updated_booking
            
    raise HTTPException(status_code=404, detail="Booking not found")

@router.patch("/{booking_id}/status", response_model=Booking)
def update_booking_status(booking_id: str, new_status: BookingStatus):
    bookings = get_bookings_data()
    
    for i, booking in enumerate(bookings):
        if booking["booking_id"] == booking_id:
            # Get current status
            current_status = booking.get("status", BookingStatus.PENDING)
            
            # Define allowed transitions
            allowed_transitions = {
                BookingStatus.PENDING: [BookingStatus.CONFIRMED, BookingStatus.CANCELLED],
                BookingStatus.CONFIRMED: [BookingStatus.CANCELLED],
                # No transitions allowed from CANCELLED or COMPLETED
                BookingStatus.CANCELLED: [],
                BookingStatus.COMPLETED: []
            }
            
            # Check if the transition is allowed
            if new_status not in allowed_transitions.get(current_status, []):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Status transition from '{current_status}' to '{new_status}' is not allowed. " 
                           f"Allowed transitions from '{current_status}': {allowed_transitions.get(current_status, [])}"
                )
            
            # Update status and timestamp if transition is allowed
            booking["status"] = new_status
            booking["updated_at"] = datetime.now().isoformat()
            bookings[i] = booking
            save_bookings_data(bookings)
            return booking
            
    raise HTTPException(status_code=404, detail="Booking not found")

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_id: str):
    bookings = get_bookings_data()
    
    for i, booking in enumerate(bookings):
        if booking["booking_id"] == booking_id:
            del bookings[i]
            save_bookings_data(bookings)
            return
            
    raise HTTPException(status_code=404, detail="Booking not found")

@router.get(
    "/{booking_id}/summary", 
    response_model=BookingSummary,
    summary="Get a booking summary",
    description="Returns a simplified view of a booking with only essential information"
)
def get_booking_summary(booking_id: str):
    """
    Retrieve a simplified summary of a booking including only:
    - destination
    - start_date
    - end_date
    - status
    
    All other fields are omitted for a cleaner response.
    """
    try:
        bookings = get_bookings_data()
        
        for booking in bookings:
            if booking["booking_id"] == booking_id:
                # Create a summary with only the required fields
                summary = {
                    "destination": booking["destination"],
                    "start_date": booking["start_date"],
                    "end_date": booking["end_date"],
                    "status": booking["status"]
                }
                
                # Use the Pydantic model to validate and parse the dates
                return BookingSummary(**summary)
                
        raise HTTPException(status_code=404, detail="Booking not found")
        
    except Exception as e:
        # Handle any unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving booking summary: {str(e)}"
        )
    
@router.get("/stats", response_model=BookingStats)
def get_booking_stats():
    """
    Get statistical information about bookings:
    - Total number of bookings
    - Number of bookings per status
    - Average duration in days
    """
    bookings = get_bookings_data()
    
    # Calculate total bookings
    total_bookings = len(bookings)
    print(total_bookings)
    
    # Count bookings by status
    status_counter = Counter(booking.get("status", "pending") for booking in bookings)
    bookings_by_status = dict(status_counter)
    
    # Calculate average duration
    durations = []
    for booking in bookings:
        try:
            start_date = datetime.fromisoformat(booking.get("start_date")).date()
            end_date = datetime.fromisoformat(booking.get("end_date")).date()
            duration = (end_date - start_date).days
            if duration >= 0:  # Ensure we only count valid durations
                durations.append(duration)
        except (ValueError, TypeError):
            # Skip invalid date formats
            continue
    
    # Calculate average duration (default to 0 if no valid durations)
    average_duration = mean(durations) if durations else 0.0
    
    return {
        "total_bookings": total_bookings,
        "bookings_by_status": bookings_by_status,
        "average_duration_days": average_duration
    }