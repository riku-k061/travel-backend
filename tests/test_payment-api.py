import pytest
import json
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from typing import Dict, List, Any

from app.main import app
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentSummary

client = TestClient(app)

# ----------------------- Test Data -----------------------

@pytest.fixture
def sample_payment_id():
    """Return a consistent UUID for testing"""
    return "f47ac10b-58cc-4372-a567-0e02b2c3d479"

@pytest.fixture
def sample_booking_id():
    """Return a consistent booking UUID for testing"""
    return "8fa85f64-5717-4562-b3fc-2c963f66afab"

@pytest.fixture
def sample_payments() -> List[Dict[str, Any]]:
    """Create sample payment data for testing"""
    return [
        {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "booking_id": "8fa85f64-5717-4562-b3fc-2c963f66afab",
            "method": "credit_card",
            "amount": 1299.99,
            "status": "pending",
            "transaction_date": "2023-08-15T14:30:25"
        },
        {
            "id": "d5b4cd7e-32a1-4a87-9f21-43578a71ee34",
            "booking_id": "afa85f64-5717-4562-b3fc-2c963f66afad",
            "method": "paypal",
            "amount": 849.50,
            "status": "completed",
            "transaction_date": "2023-08-16T09:15:42"
        },
        {
            "id": "a1b2c3d4-e5f6-4a5b-9c8d-7e6f5a4b3c2d",
            "booking_id": "9fa85f64-5717-4562-b3fc-2c963f66afac",
            "method": "bank_transfer",
            "amount": 2450.00,
            "status": "confirmed",
            "transaction_date": "2023-08-14T11:05:33"
        },
        {
            "id": "f1e2d3c4-b5a6-7c8d-9e0f-1a2b3c4d5e6f",
            "booking_id": "9fa85f64-5717-4562-b3fc-2c963f66afac",
            "method": "cryptocurrency",
            "amount": 1750.75,
            "status": "failed",
            "transaction_date": "2023-08-16T16:22:10"
        }
    ]

@pytest.fixture
def sample_bookings() -> List[Dict[str, Any]]:
    """Create sample booking data for testing"""
    return [
        {
            "id": "e7f41c69-ccb2-4a42-a9a5-5ad4aa4b0123",
            "customer_id": "a8f5g6h7-i8j9-k0l1-m2n3-o4p5q6r7s8t9",
            "destination_id": "b2c3d4e5-f6g7-h8i9-j0k1-l2m3n4o5p6q7",
            "amount": 1299.99,  # Match this to sample payment
            "status": "confirmed",
            "start_date": "2023-09-10",
            "end_date": "2023-09-15"
        },
        {
            "id": "b2c95f1d-7c67-4bbe-a2ba-7bc3fd5c0456",
            "customer_id": "b1c2d3e4-f5g6-h7i8-j9k0-l1m2n3o4p5q6",
            "destination_id": "c3d4e5f6-g7h8-i9j0-k1l2-m3n4o5p6q7r8",
            "amount": 849.50,  # Match this to sample payment
            "status": "completed",
            "start_date": "2023-08-20",
            "end_date": "2023-08-25"
        },
        {
            "id": "c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7890",
            "customer_id": "d4e5f6g7-h8i9-j0k1-l2m3-n4o5p6q7r8s9",
            "destination_id": "e5f6g7h8-i9j0-k1l2-m3n4-o5p6q7r8s9t0",
            "amount": 2450.00,  # Match this to sample payment
            "status": "confirmed",
            "start_date": "2023-08-15",
            "end_date": "2023-08-22"
        },
        {
            "id": "d4e5f6g7-h8i9-j0k1-l2m3-n4o5p6q7r8s9",
            "customer_id": "f6g7h8i9-j0k1-l2m3-n4o5-p6q7r8s9t0u1",
            "destination_id": "g7h8i9j0-k1l2-m3n4-o5p6-q7r8s9t0u1v2",
            "amount": 1750.75,  # Match this to sample payment
            "status": "canceled",
            "start_date": "2023-08-25",
            "end_date": "2023-08-30"
        }
    ]

@pytest.fixture
def new_payment_data():
    """Data for creating a new payment"""
    return {
        "booking_id": "e7f41c69-ccb2-4a42-a9a5-5ad4aa4b0123",
        "method": "credit_card",
        "amount": 1299.99,
        "status": "pending",
        "transaction_date": datetime.now().isoformat()
    }

# ----------------------- Mocks -----------------------

# Setup patches for file I/O operations
@pytest.fixture(autouse=True)
def mock_file_operations():
    """Mock all file I/O operations"""
    with patch('app.routes.payments.read_payments_data') as mock_read_payments, \
         patch('app.routes.payments.write_payments_data') as mock_write_payments, \
         patch('app.routes.payments.read_bookings_data') as mock_read_bookings, \
         patch('app.routes.payments.booking_exists') as mock_booking_exists:
        
        # Setup default return values
        mock_read_payments.return_value = []
        mock_write_payments.return_value = None
        mock_read_bookings.return_value = []
        mock_booking_exists.return_value = True
        
        yield {
            'read_payments': mock_read_payments,
            'write_payments': mock_write_payments,
            'read_bookings': mock_read_bookings,
            'booking_exists': mock_booking_exists
        }

# ----------------------- Tests -----------------------

# Create Payment Tests
class TestCreatePayment:
    def test_create_payment_success(self, mock_file_operations, new_payment_data, sample_bookings):
        """Test successful payment creation"""
        # Setup mocks
        mock_file_operations['booking_exists'].return_value = True
        mock_file_operations['read_bookings'].return_value = sample_bookings
        
        # Make request
        response = client.post("/payments/", json=new_payment_data)
        
        # Verify response
        assert response.status_code == 201
        response_data = response.json()
        assert "id" in response_data
        assert response_data["booking_id"] == new_payment_data["booking_id"]
        assert response_data["method"] == new_payment_data["method"]
        assert float(response_data["amount"]) == new_payment_data["amount"]
        
        # Verify data was saved
        mock_file_operations['write_payments'].assert_called_once()
    
    def test_create_payment_invalid_booking(self, mock_file_operations, new_payment_data):
        """Test payment creation with invalid booking ID"""
        # Setup mocks to indicate booking doesn't exist
        mock_file_operations['booking_exists'].return_value = False
        
        # Make request
        response = client.post("/payments/", json=new_payment_data)
        
        # Verify response
        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]
        
        # Verify data was not saved
        mock_file_operations['write_payments'].assert_not_called()

# Retrieve Payment Tests
class TestGetPayment:
    def test_get_payment_success(self, mock_file_operations, sample_payment_id, sample_payments):
        """Test successfully retrieving a single payment"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request
        response = client.get(f"/payments/{sample_payment_id}")
        
        # Verify response
        assert response.status_code == 200
        payment = response.json()
        assert payment["id"] == sample_payment_id
        assert payment["method"] == "credit_card"
        assert float(payment["amount"]) == 1299.99
    
    def test_get_payment_not_found(self, mock_file_operations):
        """Test retrieving a non-existent payment"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = []
        
        # Make request with a random UUID
        response = client.get(f"/payments/{uuid4()}")
        
        # Verify response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

# Update Payment Tests
class TestUpdatePayment:
    def test_update_payment_success(self, mock_file_operations, sample_payment_id, sample_payments):
        """Test successfully updating a payment"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        mock_file_operations['booking_exists'].return_value = True
        
        update_data = {
            "booking_id": sample_payments[0]["booking_id"],
            "method": "paypal",  # Changed from credit_card
            "amount": 1399.99,   # Changed amount
            "status": "pending",
            "transaction_date": datetime.now().isoformat()
        }
        
        # Make request
        response = client.put(f"/payments/{sample_payment_id}", json=update_data)
        
        # Verify response
        assert response.status_code == 200
        payment = response.json()
        assert payment["id"] == sample_payment_id
        assert payment["method"] == "paypal"  # Verify method was updated
        assert float(payment["amount"]) == 1399.99  # Verify amount was updated
        
        # Verify data was saved
        mock_file_operations['write_payments'].assert_called_once()
    
    def test_update_payment_not_found(self, mock_file_operations):
        """Test updating a non-existent payment"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = []
        mock_file_operations['booking_exists'].return_value = True
        
        update_data = {
            "booking_id": "e7f41c69-ccb2-4a42-a9a5-5ad4aa4b0123",
            "method": "paypal",
            "amount": 1399.99,
            "status": "pending",
            "transaction_date": datetime.now().isoformat()
        }
        
        # Make request with a random UUID
        response = client.put(f"/payments/{uuid4()}", json=update_data)
        
        # Verify response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        
        # Verify no data was saved
        mock_file_operations['write_payments'].assert_not_called()

# Delete Payment Tests
class TestDeletePayment:
    def test_delete_payment_success(self, mock_file_operations, sample_payment_id, sample_payments):
        """Test successfully deleting a payment"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request
        response = client.delete(f"/payments/{sample_payment_id}")
        
        # Verify response
        assert response.status_code == 204
        
        # Verify data was saved (with payment removed)
        mock_file_operations['write_payments'].assert_called_once()
    
    def test_delete_payment_not_found(self, mock_file_operations):
        """Test deleting a non-existent payment"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = []
        
        # Make request with a random UUID
        response = client.delete(f"/payments/{uuid4()}")
        
        # Verify response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        
        # Verify no data was saved
        mock_file_operations['write_payments'].assert_not_called()

# List Payments Tests
class TestListPayments:
    def test_list_payments_no_filters(self, mock_file_operations, sample_payments):
        """Test listing all payments without filters"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request
        response = client.get("/payments/")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "metadata" in data
        assert len(data["items"]) == len(sample_payments)
        assert data["metadata"]["total_count"] == len(sample_payments)
        assert data["metadata"]["filtered_count"] == len(sample_payments)
    
    def test_list_payments_with_filters(self, mock_file_operations, sample_payments):
        """Test listing payments with status filter"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request with filter
        response = client.get("/payments/?status=completed")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1  # Only one payment is completed
        assert data["items"][0]["status"] == "completed"
        assert data["metadata"]["filtered_count"] == 1
        assert "status" in data["metadata"]["filters_applied"]
    
    def test_list_payments_pagination(self, mock_file_operations, sample_payments):
        """Test pagination of payment list"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request with pagination
        response = client.get("/payments/?limit=2&offset=1")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2  # Should return 2 items
        assert data["metadata"]["limit"] == 2
        assert data["metadata"]["offset"] == 1
        assert data["metadata"]["total_count"] == len(sample_payments)
    
    def test_list_payments_amount_range(self, mock_file_operations, sample_payments):
        """Test filtering payments by amount range"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request with amount filter
        response = client.get("/payments/?min_amount=1000&max_amount=2000")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        # Should include only payments between 1000-2000
        assert len(data["items"]) == 2  
        for item in data["items"]:
            amount = float(item["amount"])
            assert 1000 <= amount <= 2000

# Confirm Payment Tests
class TestConfirmPayment:
    def test_confirm_payment_already_confirmed(self, mock_file_operations, sample_payments):
        """Test confirming an already confirmed payment"""
        # Setup mocks
        already_confirmed_id = "a1b2c3d4-e5f6-4a5b-9c8d-7e6f5a4b3c2d"  # This payment is already confirmed
        mock_file_operations['read_payments'].return_value = sample_payments
        mock_file_operations['read_bookings'].return_value = []
        
        # Make request
        response = client.patch(f"/payments/{already_confirmed_id}/confirm")
        
        # Verify response indicates payment is already confirmed
        assert response.status_code == 400
        assert "already confirmed" in response.json()["detail"]
        
        # Verify no data was saved
        mock_file_operations['write_payments'].assert_not_called()
    
    def test_confirm_payment_amount_mismatch(self, mock_file_operations, sample_payment_id, sample_payments, sample_bookings):
        """Test confirming a payment with incorrect amount"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        mock_file_operations['read_bookings'].return_value = sample_bookings
        # Make get_expected_booking_amount return a different value than the actual payment
        with patch('app.routes.payments.get_expected_booking_amount', return_value=2000.00):
            
            # Make request
            response = client.patch(f"/payments/{sample_payment_id}/confirm")
            
            # Verify response indicates amount mismatch
            assert response.status_code == 400
            
            # Verify no data was saved
            mock_file_operations['write_payments'].assert_not_called()

# Update Payment Status Tests
class TestUpdatePaymentStatus:
    def test_update_status_success(self, mock_file_operations, sample_payment_id, sample_payments):
        """Test successfully updating payment status"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request to update status to completed
        response = client.patch(f"/payments/{sample_payment_id}/status?status=completed")
        
        # Verify response
        assert response.status_code == 200
        payment = response.json()
        assert payment["id"] == sample_payment_id
        assert payment["status"] == "completed"
        
        # Verify data was saved
        mock_file_operations['write_payments'].assert_called_once()
    
    def test_update_status_not_found(self, mock_file_operations):
        """Test updating status for a non-existent payment"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = []
        
        # Make request with a random UUID
        response = client.patch(f"/payments/{uuid4()}/status?status=completed")
        
        # Verify response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        
        # Verify no data was saved
        mock_file_operations['write_payments'].assert_not_called()

# Get Payments by Booking Tests
class TestGetPaymentsByBooking:
    def test_get_payments_by_booking_success(self, mock_file_operations, sample_booking_id, sample_payments):
        """Test successfully retrieving payments for a booking"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        mock_file_operations['booking_exists'].return_value = True
        
        # Make request
        response = client.get(f"/payments/booking/{sample_booking_id}")
        
        # Verify response
        assert response.status_code == 200
        payments = response.json()
        assert len(payments) == 1
        assert payments[0]["booking_id"] == sample_booking_id
    
    def test_get_payments_by_booking_sorted(self, mock_file_operations, sample_booking_id, sample_payments):
        """Test retrieving payments for a booking with sorting"""
        # Create multiple payments for the same booking with different dates
        booking_payments = [
            {
                "id": str(uuid4()),
                "booking_id": sample_booking_id,
                "method": "credit_card",
                "amount": 500.00,
                "status": "pending",
                "transaction_date": (datetime.now() - timedelta(days=2)).isoformat()
            },
            {
                "id": str(uuid4()),
                "booking_id": sample_booking_id,
                "method": "credit_card",
                "amount": 799.99,
                "status": "confirmed",
                "transaction_date": datetime.now().isoformat()
            }
        ]
        
        # Add these to the sample payments
        all_payments = sample_payments + booking_payments
        
        # Setup mocks
        mock_file_operations['read_payments'].return_value = all_payments
        mock_file_operations['booking_exists'].return_value = True
        
        # Make request with sort_by_date=true
        response = client.get(f"/payments/booking/{sample_booking_id}?sort_by_date=true")
        
        # Verify response
        assert response.status_code == 200
        payments = response.json()
        assert len(payments) == 3  # Original + 2 new ones
        
        # Check that payments are sorted by date (newest first)
        # Convert ISO dates to datetime for comparison
        payment_dates = [datetime.fromisoformat(p["transaction_date"]) for p in payments]
        # Verify dates are in descending order
        assert all(payment_dates[i] >= payment_dates[i+1] for i in range(len(payment_dates)-1))
    
    def test_get_payments_by_booking_not_found(self, mock_file_operations):
        """Test retrieving payments for a non-existent booking"""
        # Setup mocks
        mock_file_operations['booking_exists'].return_value = False
        
        # Make request with a random UUID
        response = client.get(f"/payments/booking/{uuid4()}")
        
        # Verify response indicates booking not found
        assert response.status_code == 404
        assert "not exist" in response.json()["detail"]
    
    def test_get_payments_by_booking_no_payments(self, mock_file_operations, sample_booking_id):
        """Test retrieving payments for a booking with no payments"""
        # Setup mocks for booking exists but no payments
        mock_file_operations['booking_exists'].return_value = True
        mock_file_operations['read_payments'].return_value = []
        
        # Make request
        response = client.get(f"/payments/booking/{sample_booking_id}")
        
        # Verify response is empty array but successful
        assert response.status_code == 200
        assert response.json() == []

# Payment Summary Tests
class TestPaymentSummary:
    def test_payment_summary_all_data(self, mock_file_operations, sample_payments):
        """Test generating a summary of all payment data"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Make request
        response = client.get("/payments/summary")
        
        # Verify response
        assert response.status_code == 200
        summary = response.json()
        
        # Check overall stats
        assert summary["total_payments"] == len(sample_payments)
        assert "total_amount" in summary
        assert "average_amount" in summary
        assert "min_amount" in summary
        assert "max_amount" in summary
        
        # Check breakdowns
        assert "by_method" in summary
        assert "by_status" in summary
        assert len(summary["by_method"]) > 0
        assert len(summary["by_status"]) > 0
        
        # Check time info
        assert "earliest_payment_date" in summary
        assert "latest_payment_date" in summary
    
    def test_payment_summary_with_date_range(self, mock_file_operations, sample_payments):
        """Test generating a summary with date range filter"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = sample_payments
        
        # Define date range to include only some payments
        today = date.today()
        date_from = (today - timedelta(days=7)).isoformat()
        date_to = today.isoformat()
        
        # Make request with date range
        response = client.get(f"/payments/summary?date_from={date_from}&date_to={date_to}")
        
        # Verify response
        assert response.status_code == 200
        summary = response.json()
        
        # Check date range is reflected in metadata
        assert summary["date_range_start"] == date_from
        assert summary["date_range_end"] == date_to
    
    def test_payment_summary_invalid_date_range(self, mock_file_operations):
        """Test summary with invalid date range"""
        # Setup mocks
        mock_file_operations['read_payments'].return_value = []
        
        # Set end date before start date
        today = date.today()
        date_from = today.isoformat()
        date_to = (today - timedelta(days=7)).isoformat()
        
        # Make request with invalid date range
        response = client.get(f"/payments/summary?date_from={date_from}&date_to={date_to}")
        
        # Verify response indicates error
        assert response.status_code == 400
        assert "date_from cannot be later than date_to" in response.json()["detail"]