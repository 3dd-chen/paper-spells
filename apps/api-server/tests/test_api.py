import os

# Override environment BEFORE importing the app so MockProvider is always used
os.environ["AI_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_paper_spells.db"

import pytest
from fastapi.testclient import TestClient
from app.main import app

_TINY_PNG_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_upload_artwork():
    with TestClient(app) as client:
        response = client.post("/api/upload", json={"image_data": _TINY_PNG_B64})
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "generating"


def test_upload_then_gallery_shows_completed():
    """MockProvider completes immediately, so gallery should show the artwork."""
    with TestClient(app) as client:
        upload_res = client.post("/api/upload", json={"image_data": _TINY_PNG_B64})
        assert upload_res.status_code == 200
        task_id = upload_res.json()["task_id"]

        gallery_res = client.get("/api/gallery")
        assert gallery_res.status_code == 200
        data = gallery_res.json()
        assert isinstance(data, list)

        ids = [item["id"] for item in data]
        assert task_id in ids

        our_item = next(item for item in data if item["id"] == task_id)
        assert our_item["video_url"] is not None


def test_gallery_empty_or_list():
    with TestClient(app) as client:
        response = client.get("/api/gallery")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
