import pytest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open
import uuid

from app.main import app
from app.models.schedule import Schedule, ScheduleCreate, ScheduleUpdate, StatusSummary

client = TestClient(app)

# Mock data for tests
valid_destination_id = "789e4567-e89b-12d3-a456-426614174001"
invalid_destination_id = "invalid-destination-id"
valid_schedule_id = "123e4567-e89b-12d3-a456-426614174000"
nonexistent_schedule_id = "999e4567-e89b-12d3-a456-426614174999"

# Mock schedule data
mock_schedules = [
    {
        "id": valid_schedule_id,
        "destination_id": valid_destination_id,
        "date": datetime.now().isoformat(),
        "capacity": 30,
        "status": "active"
    }
]

# Mock destinations data
mock_destinations = [
    {
        "destination_id": valid_destination_id,
        "name": "Test Destination",
        "description": "A test destination"
    }
]

# Helper function to convert datetime objects in schedules to iso format for mocks
def prepare_schedules_for_json(schedules):
    data = []
    for schedule in schedules:
        schedule_dict = schedule.copy()
        if isinstance(schedule_dict.get("date"), datetime):
            schedule_dict["date"] = schedule_dict["date"].isoformat()
        data.append(schedule_dict)
    return data


# Mocking the json load and dump functions
@pytest.fixture
def mock_json_files(monkeypatch):
    # Mock the file operations
    def mock_load_schedules(*args, **kwargs):
        return mock_schedules
    
    def mock_destination_exists(destination_id):
        return destination_id == valid_destination_id
    
    # Apply the monkeypatches
    from app.routes import schedules
    monkeypatch.setattr(schedules, "load_schedules", mock_load_schedules)
    monkeypatch.setattr(schedules, "destination_exists", mock_destination_exists)
    
    # Mock the file open and json dump operations
    m = mock_open()
    monkeypatch.setattr("builtins.open", m)
    monkeypatch.setattr(json, "dump", lambda *args, **kwargs: None)
    
    return m


# Helper function to create a test datetime
def test_datetime():
    return datetime.now().replace(microsecond=0)


# ==================== GET ALL SCHEDULES TESTS ====================
def test_get_all_schedules(mock_json_files):
    """Test successfully retrieving all schedules"""
    response = client.get("/schedules/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == len(mock_schedules)


def test_get_schedules_with_destination_filter(mock_json_files):
    """Test filtering schedules by destination_id"""
    response = client.get(f"/schedules/?destination_id={valid_destination_id}")
    assert response.status_code == 200
    data = response.json()
    assert all(schedule["destination_id"] == valid_destination_id for schedule in data)


def test_get_schedules_with_date_range_filter(mock_json_files):
    """Test filtering schedules by date range"""
    # Prepare dates for testing (one day before and after current mock schedule)
    start_date = (datetime.now() - timedelta(days=1)).isoformat() + "Z"
    end_date = (datetime.now() + timedelta(days=1)).isoformat() + "Z"
    
    response = client.get(f"/schedules/?start_date={start_date}&end_date={end_date}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_schedules_with_invalid_sort_parameter(mock_json_files):
    """Test error handling for invalid sort parameter"""
    response = client.get("/schedules/?sort=invalid")
    assert response.status_code == 400
    assert "Sort parameter must be either 'asc' or 'desc'" in response.json()["detail"]


def test_get_schedules_with_invalid_date_format(mock_json_files):
    """Test error handling for invalid date format"""
    invalid_date = "not-a-date"
    response = client.get(f"/schedules/?start_date={invalid_date}")
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


# ==================== GET SCHEDULE BY ID TESTS ====================
def test_get_schedule_by_id_success(mock_json_files):
    """Test successfully retrieving a schedule by ID"""
    response = client.get(f"/schedules/{valid_schedule_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == valid_schedule_id


def test_get_schedule_by_id_not_found(mock_json_files):
    """Test error when schedule ID does not exist"""
    response = client.get(f"/schedules/{nonexistent_schedule_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ==================== CREATE SCHEDULE TESTS ====================
def test_create_schedule_success(mock_json_files):
    """Test successfully creating a new schedule"""
    new_schedule = {
        "destination_id": valid_destination_id,
        "date": datetime.now().isoformat(),
        "capacity": 25,
        "status": "active"
    }
    
    # Need to patch uuid generation to get a predictable result
    with patch('uuid.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-567812345678')):
        response = client.post("/schedules/", json=new_schedule)
    
    assert response.status_code == 201
    created_schedule = response.json()
    assert created_schedule["destination_id"] == new_schedule["destination_id"]
    assert created_schedule["capacity"] == new_schedule["capacity"]
    assert created_schedule["status"] == new_schedule["status"]
    assert "id" in created_schedule  # Verify ID was generated


def test_create_schedule_invalid_destination(mock_json_files):
    """Test error when creating a schedule with non-existent destination"""
    new_schedule = {
        "destination_id": invalid_destination_id,
        "date": datetime.now().isoformat(),
        "capacity": 25,
        "status": "active"
    }
    
    response = client.post("/schedules/", json=new_schedule)
    assert response.status_code == 400
    assert "destination" in response.json()["detail"].lower()


def test_create_schedule_invalid_status(mock_json_files):
    """Test error when creating a schedule with invalid status"""
    new_schedule = {
        "destination_id": valid_destination_id,
        "date": datetime.now().isoformat(),
        "capacity": 25,
        "status": "invalid_status"  # Invalid status value
    }
    
    response = client.post("/schedules/", json=new_schedule)
    assert response.status_code == 400
    assert "status" in response.json()["detail"].lower()


def test_create_schedule_invalid_capacity(mock_json_files):
    """Test error when creating a schedule with invalid capacity (0 or negative)"""
    new_schedule = {
        "destination_id": valid_destination_id,
        "date": datetime.now().isoformat(),
        "capacity": 0,  # Invalid capacity
        "status": "active"
    }
    
    response = client.post("/schedules/", json=new_schedule)
    assert response.status_code == 422  # Validation error
    assert "capacity" in str(response.json()["detail"]).lower()


# ==================== UPDATE SCHEDULE TESTS ====================
def test_update_schedule_success(mock_json_files):
    """Test successfully updating a schedule"""
    update_data = {
        "capacity": 50,
        "status": "inactive"
    }
    
    response = client.put(f"/schedules/{valid_schedule_id}", json=update_data)
    assert response.status_code == 200
    updated_schedule = response.json()
    assert updated_schedule["id"] == valid_schedule_id
    assert updated_schedule["capacity"] == update_data["capacity"]
    assert updated_schedule["status"] == update_data["status"]


def test_update_schedule_not_found(mock_json_files):
    """Test error when updating a non-existent schedule"""
    update_data = {
        "capacity": 50
    }
    
    response = client.put(f"/schedules/{nonexistent_schedule_id}", json=update_data)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_schedule_invalid_destination(mock_json_files):
    """Test error when updating a schedule with an invalid destination"""
    update_data = {
        "destination_id": invalid_destination_id
    }
    
    response = client.put(f"/schedules/{valid_schedule_id}", json=update_data)
    assert response.status_code == 400
    assert "destination" in response.json()["detail"].lower()


def test_update_schedule_invalid_status(mock_json_files):
    """Test error when updating a schedule with an invalid status"""
    update_data = {
        "status": "not_a_valid_status"
    }
    
    response = client.put(f"/schedules/{valid_schedule_id}", json=update_data)
    assert response.status_code == 400
    assert "status" in response.json()["detail"].lower()


def test_update_schedule_zero_capacity(mock_json_files):
    """Test error when updating a schedule with zero capacity"""
    update_data = {
        "capacity": 0
    }
    
    response = client.put(f"/schedules/{valid_schedule_id}", json=update_data)
    assert response.status_code == 422  # Validation error
    assert "capacity" in str(response.json()["detail"]).lower()


# ==================== DELETE SCHEDULE TESTS ====================
def test_delete_schedule_success(mock_json_files):
    """Test successfully deleting a schedule"""
    response = client.delete(f"/schedules/{valid_schedule_id}")
    assert response.status_code == 204
    assert response.content == b''  # No content in response


def test_delete_schedule_not_found(mock_json_files):
    """Test error when deleting a non-existent schedule"""
    response = client.delete(f"/schedules/{nonexistent_schedule_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ==================== STATUS SUMMARY TESTS ====================
def test_get_status_summary(mock_json_files):
    """Test getting schedule status summary"""
    response = client.get("/schedules/status-summary")
    assert response.status_code == 200
    summary = response.json()
    
    # Assert structure is correct
    assert "status_counts" in summary
    assert "total" in summary
    
    # Check that it contains the required statuses
    assert "active" in summary["status_counts"]
    assert "inactive" in summary["status_counts"]
    assert "archived" in summary["status_counts"]
    
    # Verify count is correct based on our mock data (1 active schedule)
    assert summary["status_counts"]["active"] == 1
    assert summary["total"] >= 1