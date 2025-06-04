# app/routes/vehicles.py
import json
import os
from typing import List, Optional, Set
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse
from app.models.vehicle import Vehicle, VehicleCreate, VehicleUpdate, PaginatedResponse
import uuid

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

# Path to the mock data file
VEHICLES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "vehicles.json")
DESTINATIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "destinations.json")

def read_vehicles():
    """Helper function to read vehicle data from JSON file"""
    try:
        with open(VEHICLES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return empty list if file doesn't exist or is invalid
        return []

def write_vehicles(vehicles):
    """Helper function to write vehicle data to JSON file"""
    os.makedirs(os.path.dirname(VEHICLES_FILE), exist_ok=True)
    with open(VEHICLES_FILE, "w") as f:
        json.dump(vehicles, f, indent=2)

def get_valid_destination_ids() -> Set[str]:
    """
    Get a set of all valid destination IDs from destinations.json
    Returns an empty set if the file doesn't exist or is invalid
    """
    try:
        with open(DESTINATIONS_FILE, "r") as f:
            destinations = json.load(f)
            return {dest["destination_id"] for dest in destinations}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Return empty set if file doesn't exist, is invalid, or missing id field
        return set()

def validate_destination_ids(destination_ids: List[str]):
    """
    Validate that all provided destination IDs exist in the system
    Raises HTTPException if any ID is invalid
    """
    if not destination_ids:
        return
        
    valid_ids = get_valid_destination_ids()
    
    # If destinations.json doesn't exist or is empty, we can't validate
    if not valid_ids:
        return
    
    invalid_ids = [dest_id for dest_id in destination_ids if dest_id not in valid_ids]
    
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid destination IDs: {', '.join(invalid_ids)}. These destinations do not exist in the system."
        )
    
@router.post("/bulk", response_model=List[Vehicle], status_code=status.HTTP_201_CREATED)
async def create_vehicles_bulk(vehicles: List[VehicleCreate]):
    """
    Bulk create multiple vehicles in a single operation.
    
    All vehicles must pass validation checks, including destination ID verification.
    If any vehicle fails validation, the entire operation fails and no vehicles are created.
    
    Parameters:
    - vehicles: List of vehicles to create, following the VehicleCreate schema
    
    Returns:
    - List of created vehicles with generated IDs
    
    Raises:
    - HTTPException 400: If any validation fails, with details about which item(s) failed
    """
    # Validate the request contains at least one vehicle
    if not vehicles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No vehicles provided for bulk creation"
        )
    
    # Collect all destination IDs across all vehicles for validation
    all_destination_ids = set()
    for idx, vehicle in enumerate(vehicles):
        if vehicle.destination_ids:
            all_destination_ids.update(vehicle.destination_ids)
    
    # Validate all destination IDs in a single check
    try:
        validate_destination_ids(list(all_destination_ids))
    except HTTPException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Validation failed: {e.detail}"
        )
    
    # Create new vehicles with generated IDs
    existing_vehicles = read_vehicles()
    new_vehicles = []
    
    for vehicle_data in vehicles:
        new_vehicle = Vehicle(
            id=f"veh-{str(uuid.uuid4())[:8]}",
            **vehicle_data.dict()
        )
        new_vehicles.append(new_vehicle)
    
    # Add all new vehicles to the existing list and write to file
    updated_vehicles = existing_vehicles + [v.dict() for v in new_vehicles]
    write_vehicles(updated_vehicles)
    
    return new_vehicles


@router.get("/", response_model=PaginatedResponse[Vehicle])
async def get_vehicles(
    available: Optional[bool] = None, 
    type: Optional[str] = None,
    destination_id: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100, description="Number of vehicles to return per page"),
    offset: int = Query(0, ge=0, description="Number of vehicles to skip")
):
    """
    Get vehicles with optional filtering and pagination.
    
    Parameters:
    - available: Filter by availability status (true/false)
    - type: Filter by vehicle type (e.g., "bus", "van")
    - destination_id: Filter by vehicles that serve a specific destination
    - limit: Maximum number of vehicles to return (default: 10, max: 100)
    - offset: Number of vehicles to skip (for pagination, default: 0)
    
    Returns:
    - A paginated response containing:
      - items: List of vehicles matching the filters
      - total_count: Total number of vehicles matching the filters (before pagination)
    """
    vehicles = read_vehicles()
    
    # Define filter functions - each returns True if vehicle matches filter criteria
    filters = []
    
    if available is not None:
        filters.append(lambda v: v["available"] == available)
    
    if type:
        filters.append(lambda v: v["type"] == type)
    
    if destination_id:
        filters.append(lambda v: destination_id in v["destination_ids"])
    
    # Apply all filters sequentially
    for filter_func in filters:
        vehicles = [v for v in vehicles if filter_func(v)]
    
    # Calculate total count before pagination
    total_count = len(vehicles)
    
    # Apply pagination
    paginated_vehicles = vehicles[offset:offset + limit]
    
    return {
        "items": paginated_vehicles,
        "total_count": total_count
    }


@router.get("/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str):
    """
    Get a specific vehicle by ID
    """
    vehicles = read_vehicles()
    for vehicle in vehicles:
        if vehicle["id"] == vehicle_id:
            return vehicle
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Vehicle with ID {vehicle_id} not found"
    )


@router.post("/", response_model=Vehicle, status_code=status.HTTP_201_CREATED)
async def create_vehicle(vehicle: VehicleCreate):
    """
    Create a new vehicle with validation of destination IDs
    """
    # Validate that all destination IDs exist
    validate_destination_ids(vehicle.destination_ids)
    
    vehicles = read_vehicles()
    
    # Create new vehicle with generated ID
    new_vehicle = Vehicle(
        id=f"veh-{str(uuid.uuid4())[:8]}",
        **vehicle.dict()
    )
    
    vehicles.append(new_vehicle.dict())
    write_vehicles(vehicles)
    
    return new_vehicle


@router.put("/{vehicle_id}", response_model=Vehicle)
async def update_vehicle(vehicle_id: str, vehicle_update: VehicleUpdate):
    """
    Update an existing vehicle with validation of destination IDs
    """
    # Only validate destination IDs if they are being updated
    if vehicle_update.destination_ids is not None:
        validate_destination_ids(vehicle_update.destination_ids)
    
    vehicles = read_vehicles()
    
    for i, vehicle in enumerate(vehicles):
        if vehicle["id"] == vehicle_id:
            # Get only the fields that were actually provided
            update_data = {k: v for k, v in vehicle_update.dict().items() if v is not None}
            
            # Update the vehicle data
            vehicles[i].update(update_data)
            write_vehicles(vehicles)
            
            return vehicles[i]
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Vehicle with ID {vehicle_id} not found"
    )


@router.delete("/{vehicle_id}")
async def deactivate_vehicle(vehicle_id: str):
    """
    Soft-delete a vehicle by marking it as unavailable (available=false).
    
    This endpoint implements a soft-delete pattern. Instead of removing the vehicle
    from the database, it preserves the record but marks it as unavailable.
    This allows maintaining historical data while preventing the vehicle from
    being assigned to new bookings.
    """
    vehicles = read_vehicles()
    
    for i, vehicle in enumerate(vehicles):
        if vehicle["id"] == vehicle_id:
            # Already deactivated
            if not vehicle["available"]:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "message": f"Vehicle with ID {vehicle_id} was already marked as unavailable",
                        "note": "This endpoint uses soft-delete: vehicles are deactivated, not removed from the system"
                    }
                )
            
            # Mark as unavailable (soft-delete)
            vehicles[i]["available"] = False
            write_vehicles(vehicles)
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"Vehicle with ID {vehicle_id} has been successfully deactivated",
                    "note": "This endpoint uses soft-delete: vehicles are deactivated, not removed from the system"
                }
            )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Vehicle with ID {vehicle_id} not found"
    )

@router.put("/{vehicle_id}/reactivate")
async def reactivate_vehicle(vehicle_id: str):
    """
    Reactivate a previously deactivated vehicle by marking it as available (available=true).
    
    This endpoint reverses the soft-delete operation, allowing vehicles to be returned
    to service after being temporarily deactivated.
    """
    vehicles = read_vehicles()
    
    for i, vehicle in enumerate(vehicles):
        if vehicle["id"] == vehicle_id:
            # Already active
            if vehicle["available"]:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "message": f"Vehicle with ID {vehicle_id} is already marked as available",
                        "note": "No changes were made as the vehicle was already in active status"
                    }
                )
            
            # Reactivate vehicle
            vehicles[i]["available"] = True
            write_vehicles(vehicles)
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"Vehicle with ID {vehicle_id} has been successfully reactivated",
                    "note": "The vehicle is now available for new bookings"
                }
            )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Vehicle with ID {vehicle_id} not found"
    )
