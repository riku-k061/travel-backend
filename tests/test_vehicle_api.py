import json
import pytest
from unittest.mock import patch, mock_open, MagicMock
from fastapi.testclient import TestClient
from app.main import app
import app.routes.vehicles as vehicles_module

client = TestClient(app)

# Test data fixtures
@pytest.fixture
def mock_vehicles():
    return [
        {
            "id": "veh-12345678",
            "type": "bus",
            "capacity": 50,
            "available": True,
            "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6", "4fa85f64-5717-4562-b3fc-2c963f66afa7"]
        },
        {
            "id": "veh-87654321",
            "type": "van",
            "capacity": 15,
            "available": False,
            "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]
        },
        {
            "id": "veh-11223344",
            "type": "bus",
            "capacity": 40,
            "available": True,
            "destination_ids": ["5fa85f64-5717-4562-b3fc-2c963f66afa8"]
        }
    ]

@pytest.fixture
def mock_destinations():
    return [
        {"id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "name": "City Center"},
        {"id": "4fa85f64-5717-4562-b3fc-2c963f66afa7", "name": "Mountain View"},
        {"id": "5fa85f64-5717-4562-b3fc-2c963f66afa8", "name": "Beach Resort"}
    ]

# Mock file operations
@pytest.fixture
def mock_file_operations(mock_vehicles, mock_destinations):
    # Create a context manager to handle all file operations
    def mock_file_handler(filename, mode, *args, **kwargs):
        mock_file = MagicMock()
        
        if filename.endswith('vehicles.json'):
            if 'r' in mode:
                mock_file.__enter__.return_value.read.return_value = json.dumps(mock_vehicles)
            elif 'w' in mode:
                # Capture written data for validation
                mock_file.write = lambda data: setattr(mock_file, 'written_data', data)
        
        elif filename.endswith('destinations.json'):
            if 'r' in mode:
                mock_file.__enter__.return_value.read.return_value = json.dumps(mock_destinations)
        
        return mock_file

    with patch('builtins.open', mock_file_handler):
        # Also patch os.makedirs to prevent directory creation
        with patch('os.makedirs'):
            yield

# Test GET /vehicles endpoint
@pytest.mark.usefixtures("mock_file_operations")
class TestGetVehicles:
    def test_get_all_vehicles(self):
        """Test getting all vehicles without filters"""
        response = client.get("/vehicles/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["items"]) == 3

    def test_get_vehicles_pagination(self):
        """Test pagination works correctly"""
        response = client.get("/vehicles/?limit=1&offset=1")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "veh-87654321"

    def test_filter_by_available(self):
        """Test filtering by availability"""
        response = client.get("/vehicles/?available=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert all(vehicle["available"] for vehicle in data["items"])

    def test_filter_by_type(self):
        """Test filtering by vehicle type"""
        response = client.get("/vehicles/?type=van")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["items"][0]["type"] == "van"

    def test_filter_by_destination(self):
        """Test filtering by destination ID"""
        response = client.get("/vehicles/?destination_id=5fa85f64-5717-4562-b3fc-2c963f66afa8")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert "5fa85f64-5717-4562-b3fc-2c963f66afa8" in data["items"][0]["destination_ids"]

    def test_combined_filters(self):
        """Test combining multiple filters"""
        response = client.get("/vehicles/?available=true&type=bus")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert all(vehicle["available"] and vehicle["type"] == "bus" 
                  for vehicle in data["items"])

# Test GET /vehicles/{id} endpoint
@pytest.mark.usefixtures("mock_file_operations")
class TestGetVehicleById:
    def test_get_existing_vehicle(self):
        """Test getting a vehicle that exists"""
        response = client.get("/vehicles/veh-12345678")
        assert response.status_code == 200
        vehicle = response.json()
        assert vehicle["id"] == "veh-12345678"
        assert vehicle["type"] == "bus"

    def test_get_nonexistent_vehicle(self):
        """Test getting a vehicle that doesn't exist"""
        response = client.get("/vehicles/veh-nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

# Test POST /vehicles endpoint
@pytest.mark.usefixtures("mock_file_operations")
class TestCreateVehicle:
    def test_create_valid_vehicle(self, mock_vehicles):
        """Test creating a vehicle with valid data"""
        # Patch uuid to get a predictable ID
        with patch('uuid.uuid4', return_value='test-uuid-fixed'):
            new_vehicle = {
                "type": "minibus",
                "capacity": 25,
                "available": True,
                "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]
            }
            response = client.post("/vehicles/", json=new_vehicle)
            assert response.status_code == 201
            created = response.json()
            assert created["id"].startswith("veh-")
            assert created["type"] == "minibus"
            assert created["capacity"] == 25

    def test_create_vehicle_invalid_destination(self, mock_vehicles):
        """Test creating a vehicle with invalid destination IDs"""
        # Mock the validate_destination_ids function to raise an exception
        with patch.object(vehicles_module, 'validate_destination_ids', 
                         side_effect=lambda ids: exec(
                             'raise vehicles_module.HTTPException(status_code=400, detail="Invalid destinations")' 
                             if 'invalid-dest' in ids else 'pass')):
            
            new_vehicle = {
                "type": "minibus",
                "capacity": 25,
                "available": True,
                "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6", "invalid-dest"]
            }
            response = client.post("/vehicles/", json=new_vehicle)
            assert response.status_code == 400
            assert "Invalid destinations" in response.json()["detail"]

# Test PUT /vehicles/{id} endpoint
@pytest.mark.usefixtures("mock_file_operations")
class TestUpdateVehicle:
    def test_update_existing_vehicle(self):
        """Test updating a vehicle that exists"""
        update_data = {
            "capacity": 55,
            "type": "luxury-bus"
        }
        response = client.put("/vehicles/veh-12345678", json=update_data)
        assert response.status_code == 200
        updated = response.json()
        assert updated["id"] == "veh-12345678"
        assert updated["capacity"] == 55
        assert updated["type"] == "luxury-bus"
        # Other fields should remain unchanged
        assert updated["available"] is True

    def test_update_nonexistent_vehicle(self):
        """Test updating a vehicle that doesn't exist"""
        update_data = {"capacity": 55}
        response = client.put("/vehicles/veh-nonexistent", json=update_data)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_with_invalid_destination(self):
        """Test updating a vehicle with invalid destination IDs"""
        with patch.object(vehicles_module, 'validate_destination_ids', 
                         side_effect=lambda ids: exec(
                             'raise vehicles_module.HTTPException(status_code=400, detail="Invalid destinations")' 
                             if 'invalid-dest' in ids else 'pass')):
            
            update_data = {"destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6", "invalid-dest"]}
            response = client.put("/vehicles/veh-12345678", json=update_data)
            assert response.status_code == 400
            assert "Invalid destinations" in response.json()["detail"]

# Test DELETE /vehicles/{id} endpoint (soft delete)
@pytest.mark.usefixtures("mock_file_operations")
class TestDeactivateVehicle:
    def test_deactivate_available_vehicle(self):
        """Test deactivating (soft-deleting) an available vehicle"""
        response = client.delete("/vehicles/veh-12345678")
        assert response.status_code == 200
        assert "successfully deactivated" in response.json()["message"]

    def test_deactivate_already_unavailable_vehicle(self):
        """Test deactivating a vehicle that's already unavailable"""
        response = client.delete("/vehicles/veh-87654321")
        assert response.status_code == 200
        assert "already marked as unavailable" in response.json()["message"]

    def test_deactivate_nonexistent_vehicle(self):
        """Test deactivating a vehicle that doesn't exist"""
        response = client.delete("/vehicles/veh-nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

# Test PUT /vehicles/{id}/reactivate endpoint
@pytest.mark.usefixtures("mock_file_operations")
class TestReactivateVehicle:
    def test_reactivate_unavailable_vehicle(self):
        """Test reactivating an unavailable vehicle"""
        response = client.put("/vehicles/veh-87654321/reactivate")
        assert response.status_code == 200
        assert "successfully reactivated" in response.json()["message"]

    def test_reactivate_already_available_vehicle(self):
        """Test reactivating a vehicle that's already available"""
        response = client.put("/vehicles/veh-12345678/reactivate")
        assert response.status_code == 200
        assert "already marked as available" in response.json()["message"]

    def test_reactivate_nonexistent_vehicle(self):
        """Test reactivating a vehicle that doesn't exist"""
        response = client.put("/vehicles/veh-nonexistent/reactivate")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

# Test POST /vehicles/bulk endpoint
@pytest.mark.usefixtures("mock_file_operations")
class TestBulkCreateVehicles:
    def test_bulk_create_valid_vehicles(self):
        """Test bulk creating multiple valid vehicles"""
        with patch('uuid.uuid4', side_effect=['bulk-uuid-1', 'bulk-uuid-2']):
            new_vehicles = [
                {
                    "type": "minibus",
                    "capacity": 25,
                    "available": True,
                    "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]
                },
                {
                    "type": "shuttle",
                    "capacity": 10,
                    "available": True,
                    "destination_ids": ["4fa85f64-5717-4562-b3fc-2c963f66afa7"]
                }
            ]
            response = client.post("/vehicles/bulk", json=new_vehicles)
            assert response.status_code == 201
            created = response.json()
            assert len(created) == 2
            assert all(v["id"].startswith("veh-") for v in created)
            assert created[0]["type"] == "minibus"
            assert created[1]["type"] == "shuttle"

    def test_bulk_create_with_invalid_destination(self):
        """Test bulk creating vehicles with at least one having invalid destination"""
        with patch.object(vehicles_module, 'validate_destination_ids', 
                         side_effect=lambda ids: exec(
                             'raise vehicles_module.HTTPException(status_code=400, detail="Invalid destinations")' 
                             if 'invalid-dest' in ids else 'pass')):
            
            new_vehicles = [
                {
                    "type": "minibus",
                    "capacity": 25,
                    "available": True,
                    "destination_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]
                },
                {
                    "type": "shuttle",
                    "capacity": 10,
                    "available": True,
                    "destination_ids": ["invalid-dest"]
                }
            ]
            response = client.post("/vehicles/bulk", json=new_vehicles)
            assert response.status_code == 400
            assert "Invalid destinations" in response.json()["detail"]

    def test_bulk_create_empty_list(self):
        """Test bulk creating with empty list"""
        response = client.post("/vehicles/bulk", json=[])
        assert response.status_code == 400
        assert "No vehicles provided" in response.json()["detail"]