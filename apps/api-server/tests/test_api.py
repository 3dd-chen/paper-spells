import pytest
from fastapi.testclient import TestClient
from main import app

def test_upload_artwork():
    with TestClient(app) as client:
        payload = {"image_data": "data:image/png;base64,mock"}
        response = client.post("/api/upload", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"

def test_get_status():
    with TestClient(app) as client:
        payload = {"image_data": "data:image/png;base64,mock"}
        upload_response = client.post("/api/upload", json=payload)
        task_id = upload_response.json()["task_id"]

        status_response = client.get(f"/api/status/{task_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["id"] == task_id
        assert status_data["status"] in ["pending", "completed"]

def test_get_gallery():
    with TestClient(app) as client:
        response = client.get("/api/gallery/latest")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
