import pytest
from fastapi.testclient import TestClient
from main import app


def test_upload_artwork():
    with TestClient(app) as client:
        payload = {"image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}
        response = client.post("/api/upload", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "generating"


def test_upload_then_gallery_shows_completed():
    """MockProvider completes immediately, so gallery should show the artwork."""
    with TestClient(app) as client:
        # Upload
        payload = {"image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}
        upload_res = client.post("/api/upload", json=payload)
        task_id = upload_res.json()["task_id"]

        # Gallery triggers lazy poll → MockProvider returns completed
        gallery_res = client.get("/api/gallery")
        assert gallery_res.status_code == 200
        data = gallery_res.json()
        assert isinstance(data, list)

        # Find our artwork in the gallery
        ids = [item["id"] for item in data]
        assert task_id in ids

        # Verify it has a video_url
        our_item = next(item for item in data if item["id"] == task_id)
        assert our_item["video_url"] is not None


def test_gallery_empty():
    with TestClient(app) as client:
        response = client.get("/api/gallery")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
