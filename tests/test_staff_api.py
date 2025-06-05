# tests/test_staff_api.py
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open, MagicMock

# Import the FastAPI app and staff router
from app.main import app
from app.routes import staff

# Create test client
client = TestClient(app)

# Sample test data
mock_destinations_data = [
    {"destination_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "name": "Paris, France", "description": "City of Light"},
    {"destination_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7", "name": "Rome, Italy", "description": "Eternal City"},
    {"destination_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8", "name": "Tokyo, Japan", "description": "Modern metropolis"},
]

mock_staff_data = [
    {
        "id": "staff-1",
        "name": "John Doe",
        "role": "Guide",
        "contact_email": "john.doe@example.com",
        "available": True,
        "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6", "4fa85f64-5717-4562-b3fc-2c963f66afa7"]
    },
    {
        "id": "staff-2",
        "name": "Jane Smith",
        "role": "Driver",
        "contact_email": "jane.smith@example.com",
        "available": True,
        "destination_ids": None
    },
    {
        "id": "staff-3",
        "name": "Bob Johnson",
        "role": "Guide",
        "contact_email": "bob.johnson@example.com",
        "available": False,
        "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6", "5fa85f64-5717-4562-b3fc-2c963f66afa8"]
    }
]

# Patched open function that returns different mock data for different files
class MockOpen:
    def __init__(self, mock_data):
        self.mock_data = mock_data
        
    def __call__(self, file_name, *args, **kwargs):
        if 'staff.json' in file_name:
            return mock_open(read_data=json.dumps(self.mock_data.get('staff', [])))(file_name, *args, **kwargs)
        elif 'destinations.json' in file_name:
            return mock_open(read_data=json.dumps(self.mock_data.get('destinations', [])))(file_name, *args, **kwargs)
        return mock_open()(file_name, *args, **kwargs)


# Fixture to set up mock data and patching
@pytest.fixture
def mock_file_io():
    mock_data = {
        'staff': mock_staff_data.copy(),
        'destinations': mock_destinations_data.copy()
    }
    
    # Create a mock for the open function
    mock_open_func = MockOpen(mock_data)
    
    # Mock the json.dump function to capture written data
    original_dump = json.dump
    
    def patched_dump(data, file_obj, *args, **kwargs):
        if hasattr(file_obj, 'name') and 'staff.json' in file_obj.name:
            mock_data['staff'] = data.copy()
        elif hasattr(file_obj, 'name') and 'destinations.json' in file_obj.name:
            mock_data['destinations'] = data.copy()
        return original_dump(data, file_obj, *args, **kwargs)
    
    # Apply the patches
    with patch('builtins.open', mock_open_func), \
         patch('json.dump', patched_dump):
        yield mock_data


# Test cases start here

# GET /staff tests
def test_get_all_staff(mock_file_io):
    """Test fetching all staff members"""
    response = client.get("/staff/")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    assert "total_count" in data
    assert data["total_count"] == 3
    assert len(data["items"]) == 3


def test_get_staff_with_pagination(mock_file_io):
    """Test staff pagination"""
    response = client.get("/staff/?limit=1&offset=1")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_count"] == 3
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "staff-2"


def test_filter_staff_by_role(mock_file_io):
    """Test filtering staff by role"""
    response = client.get("/staff/?role=guide")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_count"] == 2
    assert all("guide" in item["role"].lower() for item in data["items"])


def test_filter_staff_by_availability(mock_file_io):
    """Test filtering staff by availability"""
    response = client.get("/staff/?available=true")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_count"] == 2
    assert all(item["available"] for item in data["items"])


# GET /staff/{id} tests
def test_get_staff_by_id(mock_file_io):
    """Test fetching a specific staff member by ID"""
    response = client.get("/staff/staff-1")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == "staff-1"
    assert data["name"] == "John Doe"


def test_get_staff_by_id_not_found(mock_file_io):
    """Test fetching a non-existent staff member"""
    response = client.get("/staff/nonexistent-id")
    assert response.status_code == 404


# POST /staff tests
def test_create_staff(mock_file_io):
    """Test creating a new staff member"""
    new_staff = {
        "name": "New Staff",
        "role": "Agent",
        "contact_email": "new.staff@example.com",
        "available": True
    }
    
    response = client.post("/staff/", json=new_staff)
    assert response.status_code == 201
    
    data = response.json()
    assert data["name"] == "New Staff"
    assert data["role"] == "Agent"
    assert "id" in data
    
    # Verify the staff was added to mock data
    assert len(mock_file_io["staff"]) == 3


def test_create_guide_without_destinations(mock_file_io):
    """Test validation logic for creating a guide without destination IDs"""
    new_guide = {
        "name": "Invalid Guide",
        "role": "Guide",
        "contact_email": "invalid.guide@example.com",
        "available": True
    }
    
    response = client.post("/staff/", json=new_guide)
    assert response.status_code == 400


def test_create_guide_with_invalid_destination(mock_file_io):
    """Test validation logic for creating a guide with non-existent destination ID"""
    new_guide = {
        "name": "Invalid Guide",
        "role": "Guide",
        "contact_email": "invalid.guide@example.com",
        "available": True,
        "destination_ids": ["nonexistent-dest"]
    }
    
    response = client.post("/staff/", json=new_guide)
    assert response.status_code == 400
    assert "destination id" in response.json()["detail"].lower()
    assert "does not exist" in response.json()["detail"].lower()


def test_create_staff_duplicate_email(mock_file_io):
    """Test validation for duplicate email addresses"""
    duplicate_email_staff = {
        "name": "Duplicate Email",
        "role": "Driver",
        "contact_email": "john.doe@example.com",  # Already exists
        "available": True
    }
    
    response = client.post("/staff/", json=duplicate_email_staff)
    assert response.status_code == 400
    assert "email already in use" in response.json()["detail"].lower()


# PUT /staff/{id} tests
def test_update_staff(mock_file_io):
    """Test updating a staff member"""
    update_data = {
        "name": "Updated Name",
        "available": False
    }
    
    response = client.put("/staff/staff-1", json=update_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == "staff-1"
    assert data["name"] == "Updated Name"
    assert data["available"] is False
    assert data["role"] == "Guide"  # Unchanged field
    
    # Verify the staff was updated in mock data
    updated_staff = next(s for s in mock_file_io["staff"] if s["id"] == "staff-1")
    assert updated_staff["name"] == "John Doe"


def test_update_staff_not_found(mock_file_io):
    """Test updating a non-existent staff member"""
    update_data = {"name": "Updated Name"}
    
    response = client.put("/staff/nonexistent-id", json=update_data)
    assert response.status_code == 404


def test_update_guide_destinations(mock_file_io):
    """Test updating a guide's destination IDs"""
    update_data = {
        "destination_ids": ["4fa85f64-5717-4562-b3fc-2c963f66afa7"]
    }
    
    response = client.put("/staff/staff-1", json=update_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["destination_ids"] == ["4fa85f64-5717-4562-b3fc-2c963f66afa7"]


def test_update_email_unique_validation(mock_file_io):
    """Test validation when updating email to an already used one"""
    update_data = {
        "contact_email": "jane.smith@example.com"  # Used by staff-2
    }
    
    response = client.put("/staff/staff-1", json=update_data)
    assert response.status_code == 400
    assert "email already in use" in response.json()["detail"].lower()


# DELETE /staff/{id} tests (now soft delete)
def test_deactivate_staff(mock_file_io):
    """Test deactivating a staff member (soft delete)"""
    response = client.delete("/staff/staff-1")
    assert response.status_code == 200
    
    # Verify the staff was marked as unavailable but still exists
    deactivated_staff = next(s for s in mock_file_io["staff"] if s["id"] == "staff-1")
    assert deactivated_staff["available"] is True
    
    # Verify the staff was not removed
    assert len(mock_file_io["staff"]) == 3


def test_deactivate_staff_not_found(mock_file_io):
    """Test deactivating a non-existent staff member"""
    response = client.delete("/staff/nonexistent-id")
    assert response.status_code == 404


# PUT /staff/{id}/reactivate tests
def test_reactivate_staff(mock_file_io):
    """Test reactivating a deactivated staff member"""
    # First deactivate a staff member
    client.delete("/staff/staff-1")
    
    # Then reactivate
    response = client.put("/staff/staff-1/reactivate")
    assert response.status_code == 200
    
    data = response.json()
    assert data["available"] is True
    
    # Verify in mock data
    reactivated_staff = next(s for s in mock_file_io["staff"] if s["id"] == "staff-1")
    assert reactivated_staff["available"] is True


def test_reactivate_staff_not_found(mock_file_io):
    """Test reactivating a non-existent staff member"""
    response = client.put("/staff/nonexistent-id/reactivate")
    assert response.status_code == 404


# GET /staff/assigned-to/{destination_id} tests
def test_get_guides_by_destination(mock_file_io):
    """Test fetching guides assigned to a specific destination"""
    response = client.get("/staff/assigned-to/3fa85f64-5717-4562-b3fc-2c963f66afa6")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 2
    assert all("guide" in item["role"].lower() for item in data)
    assert all("3fa85f64-5717-4562-b3fc-2c963f66afa6" in item["destination_ids"] for item in data)


def test_get_guides_by_destination_filtered_by_availability(mock_file_io):
    """Test fetching available guides assigned to a destination"""
    response = client.get("/staff/assigned-to/3fa85f64-5717-4562-b3fc-2c963f66afa6?available=true")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "staff-1"
    assert data[0]["available"] is True


def test_get_guides_by_nonexistent_destination(mock_file_io):
    """Test fetching guides for a non-existent destination"""
    response = client.get("/staff/assigned-to/nonexistent-dest")
    assert response.status_code == 404


# GET /staff/summary tests
def test_get_staff_summary(mock_file_io):
    """Test fetching staff summary statistics"""
    response = client.get("/staff/summary")
    assert response.status_code == 200
    
    data = response.json()
    
    # Check structure
    assert "total_staff" in data
    assert "by_role" in data
    
    # Check totals
    assert data["total_staff"] == 3
    
    # Check role breakdown
    roles = data["by_role"]
    assert "guide" in roles
    assert "driver" in roles
    
    # Check guide stats
    guide_stats = roles["guide"]
    assert guide_stats["total"] == 2
    assert guide_stats["available"] == 1
    assert guide_stats["unavailable"] == 1
    
    # Check driver stats
    driver_stats = roles["driver"]
    assert driver_stats["total"] == 1
    assert driver_stats["available"] == 1
    assert driver_stats["unavailable"] == 0