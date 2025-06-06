# tests/test_feedback_api.py
import json
import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from pathlib import Path

from app.main import app
from app.routes.feedback import DATA_FILE, FeedbackType, FeedbackStatus

client = TestClient(app)

# Test fixture to set up and tear down test data
@pytest.fixture
def test_feedback_data(tmp_path, monkeypatch):
    """Create a temporary feedback file for testing"""
    # Create temp directory and file
    temp_dir = tmp_path / "data"
    temp_dir.mkdir()
    temp_file = temp_dir / "feedback.json"
    
    # Sample test data
    test_data = [
        {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "type": "complaint",
            "message": "Test complaint message",
            "related_booking_id": "c29a5e8a-ce47-4fbc-8a5d-48f4b8934851",
            "status": "open",
            "timestamp": "2023-09-15T14:30:25.123456",
            "admin_notes": [],
            "deleted": False
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "customer_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
            "type": "suggestion",
            "message": "Test suggestion message",
            "related_booking_id": None,
            "status": "pending",
            "timestamp": "2023-09-16T09:45:12.654321",
            "admin_notes": [],
            "deleted": False
        },
        {
            "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "customer_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
            "type": "complaint",
            "message": "Test deleted complaint",
            "related_booking_id": "d5f2d6a7-8e9b-4c1a-b2d3-9e4f5c6d7e8f",
            "status": "resolved",
            "timestamp": "2023-09-10T11:20:33.987654",
            "admin_notes": [],
            "deleted": True,
            "deletion_timestamp": "2023-09-12T10:30:45.123456"
        }
    ]
    
    # Write test data to file
    temp_file.write_text(json.dumps(test_data))
    
    # Patch the DATA_FILE path in the module
    import app.routes.feedback as feedback_routes
    monkeypatch.setattr(feedback_routes, "DATA_FILE", str(temp_file))
    
    return temp_file

# Basic CRUD tests
def test_get_all_feedback(test_feedback_data):
    """Test basic feedback listing with pagination"""
    response = client.get("/feedback")
    assert response.status_code == 200
    data = response.json()
    
    # Should return non-deleted items only
    assert data["total_count"] == 2
    assert len(data["items"]) == 2
    
    # Test pagination
    response = client.get("/feedback?limit=1&offset=1")
    data = response.json()
    assert data["total_count"] == 2  # Total count still shows all items
    assert len(data["items"]) == 1   # But only returns one item
    assert data["limit"] == 1
    assert data["offset"] == 1

def test_field_selection(test_feedback_data):
    """Test field selection functionality"""
    response = client.get("/feedback?fields=id,message,status")
    assert response.status_code == 200
    data = response.json()
    
    # Check that only specified fields are returned
    for item in data["items"]:
        assert set(item.keys()) == {"id", "message", "status"}

def test_filtering(test_feedback_data):
    """Test filtering functionality"""
    # By type
    response = client.get("/feedback?type=suggestion")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert data["items"][0]["type"] == "suggestion"

    # By status
    response = client.get("/feedback?status=open")
    data = response.json()
    assert data["total_count"] == 1
    assert data["items"][0]["status"] == "open"
    
    # Include deleted items
    response = client.get("/feedback?include_deleted=true")
    data = response.json()
    assert data["total_count"] == 3  # Now includes the deleted item

def test_get_feedback_by_id(test_feedback_data):
    """Test getting a single feedback item"""
    # Get existing feedback
    response = client.get("/feedback/f47ac10b-58cc-4372-a567-0e02b2c3d479")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    
    # Try to get deleted feedback (should fail)
    response = client.get("/feedback/6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    assert response.status_code == 404
    
    # Get deleted feedback with include_deleted flag
    response = client.get("/feedback/6ba7b810-9dad-11d1-80b4-00c04fd430c8?include_deleted=true")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

def test_create_feedback(test_feedback_data):
    """Test creating new feedback"""
    new_feedback = {
        "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "type": "complaint",
        "message": "New test complaint",
        "status": "open"
    }
    
    response = client.post("/feedback", json=new_feedback)
    assert response.status_code == 201
    data = response.json()
    
    # Check required fields
    assert "id" in data  # Should generate UUID
    assert "timestamp" in data  # Should generate timestamp
    assert data["message"] == new_feedback["message"]
    assert data["type"] == new_feedback["type"]
    
    # Verify it's retrievable
    feedback_id = data["id"]
    response = client.get(f"/feedback/{feedback_id}")
    assert response.status_code == 200

def test_update_feedback(test_feedback_data):
    """Test updating feedback"""
    update_data = {
        "message": "Updated message",
        "status": "resolved"
    }
    
    response = client.put("/feedback/f47ac10b-58cc-4372-a567-0e02b2c3d479", json=update_data)
    assert response.status_code == 200
    data = response.json()
    
    # Check fields were updated
    assert data["message"] == update_data["message"]
    assert data["status"] == update_data["status"]
    
    # Try updating deleted feedback (should fail)
    response = client.put("/feedback/6ba7b810-9dad-11d1-80b4-00c04fd430c8", json=update_data)
    assert response.status_code == 400  # Bad request - can't update deleted item

def test_admin_notes(test_feedback_data):
    """Test adding admin notes"""
    # Add note via update
    update_data = {
        "admin_note": "This is a test admin note"
    }
    
    response = client.put("/feedback/f47ac10b-58cc-4372-a567-0e02b2c3d479", json=update_data)
    assert response.status_code == 200
    data = response.json()
    
    # Check note was added
    assert len(data["admin_notes"]) == 1
    assert data["admin_notes"][0]["text"] == "This is a test admin note"
    
    # Add another note via dedicated endpoint
    note_data = {
        "note": "Second test note",
        "author": "test_admin"
    }
    
    response = client.post("/feedback/f47ac10b-58cc-4372-a567-0e02b2c3d479/notes", json=note_data)
    assert response.status_code == 200
    data = response.json()
    
    # Check both notes are present
    assert len(data["admin_notes"]) == 2
    assert data["admin_notes"][1]["text"] == "Second test note"
    assert data["admin_notes"][1]["author"] == "test_admin"

def test_soft_delete_restore(test_feedback_data):
    """Test soft delete and restore functionality"""
    # Soft delete
    response = client.delete("/feedback/f47ac10b-58cc-4372-a567-0e02b2c3d479")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    
    # Verify it no longer appears in regular listing
    response = client.get("/feedback")
    listing = response.json()
    ids = [item["id"] for item in listing["items"]]
    assert "f47ac10b-58cc-4372-a567-0e02b2c3d479" not in ids
    
    # Restore deleted feedback
    response = client.put("/feedback/f47ac10b-58cc-4372-a567-0e02b2c3d479/restore")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is False
    
    # Verify it appears again in regular listing
    response = client.get("/feedback")
    listing = response.json()
    ids = [item["id"] for item in listing["items"]]
    assert "f47ac10b-58cc-4372-a567-0e02b2c3d479" in ids

def test_summary_endpoint(test_feedback_data):
    """Test the summary statistics endpoint"""
    response = client.get("/feedback/summary")
    assert response.status_code == 200
    data = response.json()
    
    # Check basic structure
    assert "total" in data
    assert "by_type" in data
    assert "by_status" in data
    
    # Check counts (excluding deleted)
    assert data["total"] == 2
    assert data["by_type"]["complaint"] == 1
    assert data["by_type"]["suggestion"] == 1
    
    # Check with deleted included
    response = client.get("/feedback/summary?include_deleted=true")
    data = response.json()
    assert data["total"] == 3
    assert data["by_type"]["complaint"] == 2

# Admin endpoints tests
def test_bulk_import(test_feedback_data):
    """Test bulk importing feedback"""
    import_data = {
        "items": [
            {
                "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "type": "complaint",
                "message": "Bulk import test 1",
                "status": "open"
            },
            {
                "customer_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
                "type": "suggestion", 
                "message": "Bulk import test 2",
                "status": "pending"
            }
        ]
    }
    
    # Without API key (should fail)
    response = client.post("/feedback/import", json=import_data)
    assert response.status_code == 422
    
    # With API key
    headers = {"api-key": "admin-secret-key-12345"}
    response = client.post("/feedback/import", json=import_data, headers=headers)
    assert response.status_code == 201
    data = response.json()
    
    # Check all items were imported
    assert len(data) == 2
    
    # Check they appear in listing
    response = client.get("/feedback")
    listing = response.json()
    assert listing["total_count"] == 4  # 2 original + 2 imported

def test_purge_endpoint(test_feedback_data):
    """Test purging deleted feedback"""
    # Without API key (should fail)
    response = client.delete("/feedback/purge")
    assert response.status_code ==422
    
    # With API key
    headers = {"api-key": "admin-secret-key-12345"}
    response = client.delete("/feedback/purge", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    # Check purge report
    assert data["purged_count"] == 1
    assert data["remaining_count"] == 2
    
    # Verify deleted items are actually gone
    response = client.get("/feedback?include_deleted=true")
    listing = response.json()
    assert listing["total_count"] == 2  # Only non-deleted remain
    
    # Test date-based purging
    # First create and delete a new item
    new_feedback = {
        "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "type": "complaint",
        "message": "To be deleted",
        "status": "open"
    }
    response = client.post("/feedback", json=new_feedback)
    new_id = response.json()["id"]
    client.delete(f"/feedback/{new_id}")
    
    # Purge with future cutoff date
    future_date = (datetime.now() + timedelta(days=1)).isoformat()
    response = client.delete(f"/feedback/purge?deleted_before={future_date}", headers=headers)
    data = response.json()
    assert data["purged_count"] == 1 