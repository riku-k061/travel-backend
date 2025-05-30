# tests/test_booking_api.py
import json
import os
import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime, timedelta

from app.main import app
from app.models.booking import BookingStatus

client = TestClient(app)

# Test data setup
TEST_DATA_FILE = "app/data/bookings.json"

@pytest.fixture(autouse=True)
def setup_test_data():
    """
    Setup test data before each test and clean up after.
    This ensures tests have a consistent starting point.
    """
    # Create a test booking dataset
    test_bookings = [
        {
            "booking_id": "test-booking-1",
            "customer_id": "customer-1",
            "destination": "Paris",
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=7)),
            "status": "confirmed",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "booking_id": "test-booking-2",
            "customer_id": "customer-2",
            "destination": "London",
            "start_date": str(date.today() + timedelta(days=10)),
            "end_date": str(date.today() + timedelta(days=15)),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "booking_id": "test-booking-3",
            "customer_id": "customer-1",
            "destination": "Rome",
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(date.today() - timedelta(days=20)),
            "status": "completed",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    ]

    # Backup existing data if any
    if os.path.exists(TEST_DATA_FILE):
        with open(TEST_DATA_FILE, "r") as f:
            original_data = f.read()
    else:
        original_data = "[]"

    # Write test data
    with open(TEST_DATA_FILE, "w") as f:
        json.dump(test_bookings, f)

    # Yield to allow test to run
    yield

    # Restore original data
    with open(TEST_DATA_FILE, "w") as f:
        f.write(original_data)

def test_create_booking():
    """Test creating a new booking through the API."""
    booking_data = {
        "customer_id": "customer-new",
        "destination": "Tokyo",
        "start_date": str(date.today() + timedelta(days=30)),
        "end_date": str(date.today() + timedelta(days=40))
    }

    response = client.post("/bookings/", json=booking_data)
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response contains expected fields
    assert "booking_id" in data
    assert data["customer_id"] == booking_data["customer_id"]
    assert data["destination"] == booking_data["destination"]
    assert data["status"] == "pending"
    
    # Verify booking was actually saved
    get_response = client.get(f"/bookings/{data['booking_id']}")
    assert get_response.status_code == 200

def test_create_booking_invalid_dates():
    """Test creating a booking with end_date before start_date should fail."""
    booking_data = {
        "customer_id": "customer-new",
        "destination": "Tokyo",
        "start_date": str(date.today() + timedelta(days=40)),  # End date is before start date
        "end_date": str(date.today() + timedelta(days=30))
    }

    response = client.post("/bookings/", json=booking_data)
    
    # Should fail validation with 422 Unprocessable Entity
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data  # Error details should be provided

def test_get_all_bookings():
    """Test retrieving all bookings."""
    response = client.get("/bookings/")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return a list with our test bookings
    assert isinstance(data, list)
    assert len(data) >= 3  # At least our 3 test bookings

def test_get_booking_by_id():
    """Test retrieving a specific booking by ID."""
    booking_id = "test-booking-1"
    response = client.get(f"/bookings/{booking_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify correct booking is returned
    assert data["booking_id"] == booking_id
    assert data["destination"] == "Paris"

def test_get_booking_by_id_not_found():
    """Test properly handling requests for non-existent bookings."""
    booking_id = "non-existent-booking"
    response = client.get(f"/bookings/{booking_id}")
    
    assert response.status_code == 404
    assert "detail" in response.json()

def test_update_booking():
    """Test updating an existing booking."""
    booking_id = "test-booking-2"
    update_data = {
        "customer_id": "customer-2-updated",
        "destination": "New York",
        "start_date": str(date.today() + timedelta(days=20)),
        "end_date": str(date.today() + timedelta(days=25))
    }
    
    response = client.put(f"/bookings/{booking_id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify booking was updated
    assert data["booking_id"] == booking_id
    assert data["destination"] == update_data["destination"]
    assert data["customer_id"] == update_data["customer_id"]
    
    # Verify status was preserved
    assert data["status"] == "pending"
    
    # Verify updated_at was changed
    assert "updated_at" in data

def test_update_booking_status():
    """Test updating a booking's status."""
    booking_id = "test-booking-2"  # Pending booking
    
    # Change status from pending to confirmed
    response = client.patch(f"/bookings/{booking_id}/status", params={"new_status": "confirmed"})
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify status was updated
    assert data["status"] == "confirmed"

def test_update_booking_status_invalid_transition():
    """Test that invalid status transitions are rejected."""
    booking_id = "test-booking-3"  # Completed booking
    
    # Try to change status from completed to confirmed (not allowed)
    response = client.patch(f"/bookings/{booking_id}/status", params={"new_status": "confirmed"})
    
    assert response.status_code == 400
    assert "detail" in response.json()  # Should have error details

def test_delete_booking():
    """Test deleting a booking."""
    # First create a booking to delete
    booking_data = {
        "customer_id": "customer-delete",
        "destination": "Berlin",
        "start_date": str(date.today() + timedelta(days=50)),
        "end_date": str(date.today() + timedelta(days=55))
    }
    
    create_response = client.post("/bookings/", json=booking_data)
    booking_id = create_response.json()["booking_id"]
    
    # Now delete it
    delete_response = client.delete(f"/bookings/{booking_id}")
    assert delete_response.status_code == 204
    
    # Verify it's gone
    get_response = client.get(f"/bookings/{booking_id}")
    assert get_response.status_code == 404

def test_search_bookings():
    """Test filtering bookings by status and customer_id."""
    # Test filtering by status
    status_response = client.get("/bookings/search", params={"status": "pending"})
    assert status_response.status_code == 200
    status_data = status_response.json()
    
    # All returned bookings should have pending status
    assert all(booking["status"] == "pending" for booking in status_data)
    
    # Test filtering by customer_id
    customer_response = client.get("/bookings/search", params={"customer_id": "customer-1"})
    assert customer_response.status_code == 200
    customer_data = customer_response.json()
    
    # All returned bookings should have customer-1
    assert all(booking["customer_id"] == "customer-1" for booking in customer_data)
    
    # Test combined filtering
    combined_response = client.get(
        "/bookings/search", 
        params={"status": "completed", "customer_id": "customer-1"}
    )
    assert combined_response.status_code == 200
    combined_data = combined_response.json()
    
    # All returned bookings should match both filters
    assert all(
        booking["status"] == "completed" and booking["customer_id"] == "customer-1" 
        for booking in combined_data
    )

def test_booking_summary():
    """Test the booking summary endpoint."""
    booking_id = "test-booking-1"
    
    response = client.get(f"/bookings/{booking_id}/summary")
    assert response.status_code == 200
    data = response.json()
    
    # Verify summary only contains the expected fields
    expected_fields = {"destination", "start_date", "end_date", "status"}
    assert set(data.keys()) == expected_fields
    
    # Verify correct data
    assert data["destination"] == "Paris"
    assert data["status"] == "confirmed"
