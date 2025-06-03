#app/routes/payments.py
import logging
from enum import Enum
import math
from fastapi import APIRouter, HTTPException, Path, Query, Depends
from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID
import json
import os
from datetime import datetime, date
from app.models.payment import Payment, PaymentCreate, PaymentStatus, PaymentMethod, PaginatedPaymentResponse, PaymentSummary, PaymentMethodSummary, PaymentStatusSummary

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    responses={404: {"description": "Not found"}},
)

# Helper functions
def read_payments_data():
    """Read payments data from JSON file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(script_dir, "..", "data", "payments.json")
    
    try:
        with open(data_file_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Return empty list if file not found or is invalid
        return []

def write_payments_data(data):
    """Write payments data to JSON file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(script_dir, "..", "data", "payments.json")
    
    with open(data_file_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def read_bookings_data():
    """Read bookings data from JSON file to verify booking_id exists"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(script_dir, "..", "data", "bookings.json")
    
    try:
        with open(data_file_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Return empty list if file not found or is invalid
        return []

def booking_exists(booking_id: UUID) -> bool:
    """Check if a booking exists with the given booking_id"""
    bookings = read_bookings_data()
    return any(booking.get("booking_id") == str(booking_id) for booking in bookings)

@router.get("/summary", response_model=PaymentSummary)
async def get_payments_summary(
    date_from: Optional[date] = Query(None, description="Filter by transaction date from (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter by transaction date to (inclusive)")
):
    """
    Generate a summary of payment statistics.
    
    This endpoint aggregates payment data to provide insights suitable for an admin dashboard:
    - Overall payment statistics (totals, averages, etc.)
    - Breakdowns by payment method and status
    - Date range information
    
    Optional query parameters allow filtering by date range.
    """
    logger.info(f"Generating payment summary with date range: {date_from} to {date_to}")
    
    # Validate date filters
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from cannot be later than date_to"
        )
    
    # Read all payment data
    payments_data = read_payments_data()
    
    # Initialize variables for aggregation
    total_amount = 0.0
    payment_amounts = []
    method_stats = {}
    status_stats = {}
    earliest_date = None
    latest_date = None
    
    # Status specific counters
    status_counters = {
        "confirmed": {"count": 0, "amount": 0.0},
        "completed": {"count": 0, "amount": 0.0},
        "pending": {"count": 0, "amount": 0.0},
        "failed": {"count": 0, "amount": 0.0},
        "refunded": {"count": 0, "amount": 0.0},
        "canceled": {"count": 0, "amount": 0.0}
    }
    
    # Count of payments that match the filter criteria
    filtered_count = 0
    
    # Process each payment
    for payment in payments_data:
        # Parse and validate the transaction date
        try:
            if isinstance(payment.get("transaction_date"), str):
                payment_date = datetime.fromisoformat(payment["transaction_date"])
                payment_date_only = payment_date.date()
                
                # Apply date filter if provided
                if date_from is not None and payment_date_only < date_from:
                    continue
                if date_to is not None and payment_date_only > date_to:
                    continue
                
                # Track earliest and latest dates
                if earliest_date is None or payment_date < earliest_date:
                    earliest_date = payment_date
                if latest_date is None or payment_date > latest_date:
                    latest_date = payment_date
            else:
                # Skip payments with missing dates if date filter is applied
                if date_from is not None or date_to is not None:
                    continue
        except ValueError:
            # Skip payments with invalid date format
            logger.warning(f"Skipped payment with invalid date format: {payment.get('id')}")
            continue
        
        # Payment passed all filters, include it in statistics
        filtered_count += 1
        
        # Process payment amount
        try:
            amount = float(payment.get("amount", 0))
            total_amount += amount
            payment_amounts.append(amount)
            
            # Update method statistics
            method = payment.get("method", "unknown")
            if method not in method_stats:
                method_stats[method] = {"count": 0, "amount": 0.0}
            method_stats[method]["count"] += 1
            method_stats[method]["amount"] += amount
            
            # Update status statistics
            status = payment.get("status", "unknown")
            if status not in status_stats:
                status_stats[status] = {"count": 0, "amount": 0.0}
            status_stats[status]["count"] += 1
            status_stats[status]["amount"] += amount
            
            # Update status-specific counters
            for status_key in status_counters:
                if status == status_key:
                    status_counters[status_key]["count"] += 1
                    status_counters[status_key]["amount"] += amount
            
        except (ValueError, TypeError):
            logger.warning(f"Skipped payment with invalid amount: {payment.get('id')}")
            continue
    
    # Calculate aggregate statistics
    average_amount = total_amount / filtered_count if filtered_count > 0 else 0
    min_amount = min(payment_amounts) if payment_amounts else 0
    max_amount = max(payment_amounts) if payment_amounts else 0
    
    # Calculate percentage of total for each method
    method_summaries = []
    for method, stats in method_stats.items():
        method_summaries.append(PaymentMethodSummary(
            method=method,
            count=stats["count"],
            total_amount=stats["amount"],
            percentage_of_total=(stats["count"] / filtered_count * 100 if filtered_count > 0 else 0)
        ))
    
    # Calculate percentage of total for each status
    status_summaries = []
    for status, stats in status_stats.items():
        status_summaries.append(PaymentStatusSummary(
            status=status,
            count=stats["count"],
            total_amount=stats["amount"],
            percentage_of_total=(stats["count"] / filtered_count * 100 if filtered_count > 0 else 0)
        ))
    
    # Sort breakdowns by count (descending)
    method_summaries.sort(key=lambda x: x.count, reverse=True)
    status_summaries.sort(key=lambda x: x.count, reverse=True)
    
    # Create the summary response
    summary = PaymentSummary(
        # Overall statistics
        total_payments=filtered_count,
        total_amount=total_amount,
        average_amount=average_amount,
        min_amount=min_amount,
        max_amount=max_amount,
        
        # Status specific statistics
        confirmed_payments=status_counters["confirmed"]["count"],
        confirmed_amount=status_counters["confirmed"]["amount"],
        completed_payments=status_counters["completed"]["count"],
        completed_amount=status_counters["completed"]["amount"],
        pending_payments=status_counters["pending"]["count"],
        pending_amount=status_counters["pending"]["amount"],
        failed_payments=status_counters["failed"]["count"],
        failed_amount=status_counters["failed"]["amount"],
        
        # Detailed breakdowns
        by_method=method_summaries,
        by_status=status_summaries,
        
        # Time information
        earliest_payment_date=earliest_date,
        latest_payment_date=latest_date,
        date_range_start=date_from,
        date_range_end=date_to
    )
    
    logger.info(f"Generated payment summary for {filtered_count} payments with total amount {total_amount}")
    return summary

# Endpoint to get all payments
@router.get("/", response_model=PaginatedPaymentResponse)
async def get_all_payments(
    status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    method: Optional[PaymentMethod] = Query(None, description="Filter by payment method"),
    min_amount: Optional[float] = Query(None, description="Filter by minimum payment amount", ge=0),
    max_amount: Optional[float] = Query(None, description="Filter by maximum payment amount", ge=0),
    date_from: Optional[date] = Query(None, description="Filter by transaction date from (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter by transaction date to (inclusive)"),
    booking_id: Optional[UUID] = Query(None, description="Filter by booking ID"),
    limit: int = Query(10, description="Maximum number of records to return", ge=1, le=100),
    offset: int = Query(0, description="Number of records to skip for pagination", ge=0),
    sort_by: Optional[str] = Query(None, description="Field to sort by (amount, date)"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc, desc)")
):
    """
    Get all payments with extensive filtering options and paginated response.
    
    Returns a structured response containing:
    - **items**: List of payments matching the query parameters
    - **metadata**: Pagination information and applied filters
    """
    logger.debug(f"Fetching payments with filters: status={status}, method={method}, amount={min_amount}-{max_amount}")
    
    # Track which filters were applied for metadata
    filters_applied = {}
    
    # Validate amount filters
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(
            status_code=400,
            detail="min_amount cannot be greater than max_amount"
        )
    
    # Validate date filters
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from cannot be later than date_to"
        )
    
    # Populate filters_applied dictionary
    if status is not None:
        filters_applied["status"] = status.value
    if method is not None:
        filters_applied["method"] = method.value
    if min_amount is not None:
        filters_applied["min_amount"] = min_amount
    if max_amount is not None:
        filters_applied["max_amount"] = max_amount
    if date_from is not None:
        filters_applied["date_from"] = date_from.isoformat()
    if date_to is not None:
        filters_applied["date_to"] = date_to.isoformat()
    if booking_id is not None:
        filters_applied["booking_id"] = str(booking_id)
    
    payments = read_payments_data()
    filtered_results = []
    
    for payment_data in payments:
        include_payment = True
        
        # Apply status filter
        if status is not None and payment_data.get("status") != status.value:
            include_payment = False
        
        # Apply method filter
        if include_payment and method is not None and payment_data.get("method") != method.value:
            include_payment = False
        
        # Apply amount range filter
        payment_amount = float(payment_data.get("amount", 0))
        if include_payment and min_amount is not None and payment_amount < min_amount:
            include_payment = False
        if include_payment and max_amount is not None and payment_amount > max_amount:
            include_payment = False
        
        # Apply date range filter
        if include_payment and (date_from is not None or date_to is not None) and "transaction_date" in payment_data:
            try:
                if isinstance(payment_data["transaction_date"], str):
                    payment_date = datetime.fromisoformat(payment_data["transaction_date"]).date()
                    
                    if date_from is not None and payment_date < date_from:
                        include_payment = False
                    if date_to is not None and payment_date > date_to:
                        include_payment = False
            except ValueError:
                # Skip payments with invalid dates
                include_payment = False
        
        # Apply booking ID filter
        if include_payment and booking_id is not None and payment_data.get("booking_id") != str(booking_id):
            include_payment = False
            
        # If payment passes all filters, add to results
        if include_payment:
            # Convert string dates to datetime objects
            if "transaction_date" in payment_data and isinstance(payment_data["transaction_date"], str):
                try:
                    payment_data = dict(payment_data)  # Create a copy to avoid modifying the original
                    payment_data["transaction_date"] = datetime.fromisoformat(payment_data["transaction_date"])
                    filtered_results.append(Payment(**payment_data))
                except ValueError:
                    # Skip payments with invalid dates
                    logger.warning(f"Skipped payment with invalid date format: {payment_data.get('id')}")
                    continue
            else:
                filtered_results.append(Payment(**payment_data))
    
    # Get total count before sorting and pagination
    total_count = len(payments)
    filtered_count = len(filtered_results)
    
    # Apply sorting if specified
    if sort_by:
        reverse = sort_order.lower() == "desc"
        
        if sort_by == "amount":
            filtered_results.sort(key=lambda x: x.amount, reverse=reverse)
        elif sort_by == "date":
            filtered_results.sort(key=lambda x: x.transaction_date, reverse=reverse)
        # Add more sorting options as needed
    
    # Apply pagination
    paginated_results = filtered_results[offset:offset + limit]
    
    # Calculate if there are more results
    has_more = (offset + limit) < filtered_count
    
    # Calculate page information
    current_page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = (filtered_count + limit - 1) // limit if limit > 0 else 1
    
    # Create metadata
    metadata = {
        "total_count": total_count,
        "filtered_count": filtered_count,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "current_page": current_page,
        "total_pages": total_pages,
        "filters_applied": filters_applied
    }
    
    logger.info(f"Returning {len(paginated_results)} of {filtered_count} filtered payments (from {total_count} total)")
    
    # Return structured response
    return {
        "items": paginated_results,
        "metadata": metadata
    }
# Endpoint to get a single payment by ID
@router.get("/{payment_id}", response_model=Payment)
async def get_payment(
    payment_id: UUID = Path(..., description="The ID of the payment to retrieve")
):
    """
    Get a single payment by its ID
    """
    payments = read_payments_data()
    
    for payment in payments:
        if payment.get("id") == str(payment_id):
            # Convert string date to datetime object
            if "transaction_date" in payment and isinstance(payment["transaction_date"], str):
                payment["transaction_date"] = datetime.fromisoformat(payment["transaction_date"])
                
            return Payment(**payment)
            
    raise HTTPException(status_code=404, detail=f"Payment with ID {payment_id} not found")

# Endpoint to create a new payment
@router.post("/", response_model=Payment, status_code=201)
async def create_payment(payment: PaymentCreate):
    """
    Create a new payment record
    """
    payments = read_payments_data()
    
    # Verify booking exists
    if not booking_exists(payment.booking_id):
        raise HTTPException(
            status_code=400, 
            detail=f"Booking with ID {payment.booking_id} does not exist"
        )
    
    # Create a new Payment instance with an auto-generated ID
    new_payment = Payment(
        booking_id=payment.booking_id,
        method=payment.method,
        amount=payment.amount,
        status=payment.status,
        transaction_date=payment.transaction_date
    )
    
    # Convert to dict for JSON serialization
    payment_dict = new_payment.model_dump()
    
    # Convert UUID to string for storage
    payment_dict["id"] = str(payment_dict["id"])
    payment_dict["booking_id"] = str(payment_dict["booking_id"])
    
    # Convert datetime to string for storage
    payment_dict["transaction_date"] = payment_dict["transaction_date"].isoformat()
    
    # Add to our data
    payments.append(payment_dict)
    write_payments_data(payments)
    
    return new_payment

# Endpoint to update a payment
@router.put("/{payment_id}", response_model=Payment)
async def update_payment(
    payment_update: PaymentCreate,
    payment_id: UUID = Path(..., description="The ID of the payment to update")
):
    """
    Update an existing payment by ID
    """
    payments = read_payments_data()
    
    # Verify booking exists
    if not booking_exists(payment_update.booking_id):
        raise HTTPException(
            status_code=400, 
            detail=f"Booking with ID {payment_update.booking_id} does not exist"
        )
    
    # Find and update the payment
    for i, payment in enumerate(payments):
        if payment.get("id") == str(payment_id):
            # Create updated payment dict
            updated_payment = {
                "id": str(payment_id),
                "booking_id": str(payment_update.booking_id),
                "method": payment_update.method.value,
                "amount": float(payment_update.amount),
                "status": payment_update.status.value,
                "transaction_date": payment_update.transaction_date.isoformat()
            }
            
            # Update in our list
            payments[i] = updated_payment
            write_payments_data(payments)
            
            # Return as a proper Payment object
            return Payment(
                id=payment_id,
                booking_id=payment_update.booking_id,
                method=payment_update.method,
                amount=payment_update.amount,
                status=payment_update.status,
                transaction_date=payment_update.transaction_date
            )
    
    # If payment not found
    raise HTTPException(status_code=404, detail=f"Payment with ID {payment_id} not found")

# Endpoint to delete a payment
@router.delete("/{payment_id}", status_code=204)
async def delete_payment(
    payment_id: UUID = Path(..., description="The ID of the payment to delete")
):
    """
    Delete a payment by ID
    """
    payments = read_payments_data()
    initial_size = len(payments)
    
    # Filter out the payment to delete
    updated_payments = [payment for payment in payments if payment.get("id") != str(payment_id)]
    
    # If no payment was removed, it wasn't found
    if len(updated_payments) == initial_size:
        raise HTTPException(status_code=404, detail=f"Payment with ID {payment_id} not found")
    
    # Write the updated list back to the file
    write_payments_data(updated_payments)
    
    # 204 No Content response is returned automatically

# Endpoint to update payment status
@router.patch("/{payment_id}/status", response_model=Payment)
async def update_payment_status(
    status: PaymentStatus,
    payment_id: UUID = Path(..., description="The ID of the payment to update")
):
    """
    Update just the status of a payment
    """
    payments = read_payments_data()
    
    # Find and update the payment status
    for i, payment in enumerate(payments):
        if payment.get("id") == str(payment_id):
            # Update only the status
            payment["status"] = status.value
            payments[i] = payment
            write_payments_data(payments)
            
            # Convert string date to datetime object for return
            if "transaction_date" in payment and isinstance(payment["transaction_date"], str):
                payment["transaction_date"] = datetime.fromisoformat(payment["transaction_date"])
                
            return Payment(**payment)
    
    # If payment not found
    raise HTTPException(status_code=404, detail=f"Payment with ID {payment_id} not found")

# Endpoint to get payments by booking ID
@router.get("/booking/{booking_id}", response_model=List[Payment])
async def get_payments_by_booking(
    booking_id: UUID = Path(..., description="The ID of the booking to find payments for"),
    sort_by_date: Optional[bool] = Query(
        False, 
        description="Sort results by transaction date (newest first when true)"
    )
):
    """
    Get all payments associated with a specific booking.
    
    Parameters:
    - **booking_id**: UUID of the booking to find payments for
    - **sort_by_date**: When true, sorts payments by transaction date (newest first)
    
    Returns a list of payments for the specified booking. If no payments are found,
    returns an empty list with a warning status code.
    """
    logger.debug(f"Fetching payments for booking ID: {booking_id}")
    
    # Verify booking exists
    if not booking_exists(booking_id):
        logger.warning(f"Attempt to fetch payments for non-existent booking ID: {booking_id}")
        raise HTTPException(
            status_code=404, 
            detail=f"Booking with ID {booking_id} does not exist"
        )
    
    payments = read_payments_data()
    result = []
    
    logger.debug(f"Found {len(payments)} total payment records in database")
    
    for payment in payments:
        if payment.get("booking_id") == str(booking_id):
            logger.debug(f"Found payment {payment.get('id')} for booking {booking_id}")
            # Convert string date to datetime object
            if "transaction_date" in payment and isinstance(payment["transaction_date"], str):
                try:
                    payment["transaction_date"] = datetime.fromisoformat(payment["transaction_date"])
                except ValueError:
                    logger.error(f"Invalid date format in payment {payment.get('id')}: {payment.get('transaction_date')}")
                    # Skip payments with invalid dates
                    continue
            
            result.append(Payment(**payment))
    
    # Sort results by transaction date if requested
    if sort_by_date:
        logger.debug(f"Sorting {len(result)} payments by transaction date")
        result.sort(key=lambda x: x.transaction_date, reverse=True)  # Newest first
    
    # Handle the case where no payments are found
    if not result:
        logger.warning(f"No payments found for booking ID: {booking_id}")
        # We're returning a 200 OK with an empty list and a warning
        # Instead of an error, this allows the client to distinguish between
        # "booking doesn't exist" (404) and "booking exists but has no payments" (200 with empty list)
        return []
    
    logger.info(f"Returning {len(result)} payments for booking ID: {booking_id}")
    return result

def validate_payment_exists(payments: List[Dict], payment_id: UUID) -> Tuple[int, Dict]:
    """Find a payment by ID and return its index and data"""
    for i, payment in enumerate(payments):
        if payment.get("id") == str(payment_id):
            return i, payment
    
    raise HTTPException(
        status_code=404, 
        detail=f"Payment with ID {payment_id} not found"
    )

def validate_payment_status(payment: Dict) -> None:
    """Validate that payment is in a valid status for confirmation"""
    current_status = payment.get("status")
    
    # If already confirmed, provide a clear message
    if current_status == PaymentStatus.CONFIRMED.value:
        raise HTTPException(
            status_code=400,
            detail="Payment is already confirmed"
        )
    
    # Check for terminal states that can't be changed
    invalid_statuses = [
        PaymentStatus.COMPLETED.value, 
        PaymentStatus.REFUNDED.value, 
        PaymentStatus.CANCELED.value
    ]
    
    if current_status in invalid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm payment in '{current_status}' status"
        )

def validate_booking_exists(bookings: List[Dict], booking_id: str) -> Dict:
    """Find and validate the booking associated with a payment"""
    for booking in bookings:
        if booking.get("booking_id") == booking_id:
            return booking
    
    raise HTTPException(
        status_code=400,
        detail=f"Associated booking with ID {booking_id} not found"
    )

def validate_payment_amount(payment_amount: float, expected_amount: float) -> None:
    """Validate that payment amount matches expected amount using math.isclose"""
    # Using math.isclose for more reliable floating point comparison
    # rel_tol is relative tolerance, abs_tol is absolute tolerance
    if not math.isclose(payment_amount, expected_amount, rel_tol=1e-9, abs_tol=0.01):
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount {payment_amount} does not match expected amount {expected_amount}"
        )

# Refactored endpoint to confirm a payment
@router.patch("/{payment_id}/confirm", response_model=Payment)
async def confirm_payment(
    payment_id: UUID = Path(..., description="The ID of the payment to confirm")
):
    """
    Confirm a payment by validating its eligibility and updating its status.
    
    This endpoint performs several validation steps:
    1. Verifies the payment exists
    2. Checks that the payment is in a valid state for confirmation
    3. Verifies the associated booking exists
    4. Validates that the payment amount matches the expected booking price
    
    If all validations pass, the payment status is updated to "confirmed" and
    the transaction timestamp is updated to the current time.
    
    Returns the updated payment object.
    """
    logger.info(f"Processing confirmation request for payment ID: {payment_id}")
    
    # Load required data
    payments = read_payments_data()
    bookings = read_bookings_data()
    
    # Step 1: Validate payment exists
    payment_index, payment_data = validate_payment_exists(payments, payment_id)
    logger.debug(f"Found payment with ID {payment_id} at index {payment_index}")
    
    # Step 2: Validate payment status
    validate_payment_status(payment_data)
    logger.debug(f"Payment status '{payment_data.get('status')}' is valid for confirmation")
    
    # Step 3: Validate booking exists
    booking_id = payment_data.get("booking_id")
    booking_data = validate_booking_exists(bookings, booking_id)
    logger.debug(f"Validated associated booking with ID {booking_id}")
    
    # Step 4: Validate payment amount
    payment_amount = float(payment_data.get("amount", 0))
    expected_amount = get_expected_booking_amount(booking_data)
    validate_payment_amount(payment_amount, expected_amount)
    logger.debug(f"Validated payment amount {payment_amount} matches expected amount {expected_amount}")
    
    # All validations passed, confirm the payment
    payment_data["status"] = PaymentStatus.CONFIRMED.value
    payment_data["transaction_date"] = datetime.now().isoformat()
    
    # Save updated payment
    payments[payment_index] = payment_data
    write_payments_data(payments)
    logger.info(f"Payment {payment_id} successfully confirmed")
    
    # Return updated payment as a proper Payment object
    # Convert string date to datetime object for return
    updated_payment = dict(payment_data)  # Create a copy to avoid modifying the original
    updated_payment["transaction_date"] = datetime.fromisoformat(updated_payment["transaction_date"])
    
    return Payment(**updated_payment)

def get_expected_booking_amount(booking_data):
    """
    Calculate the expected amount for a booking.
    This is a simplified version - in a real system, this would calculate based on
    booking details, duration, guest count, etc.
    
    Args:
        booking_data: The booking data dictionary
    
    Returns:
        The expected amount for the booking
    """
    # Simplified calculation based on dummy data
    booking_id = booking_data.get("booking_id")
    
    # Hardcoded expected amounts by booking ID
    # In a real system, this would be calculated from the booking data
    expected_amounts = {
        "8fa85f64-5717-4562-b3fc-2c963f66afab": 1299.99,
        "9fa85f64-5717-4562-b3fc-2c963f66afa": 849.50,
        "afa85f64-5717-4562-b3fc-2c963f66afad": 2450.00
    }
    
    return expected_amounts.get(booking_id, 0)