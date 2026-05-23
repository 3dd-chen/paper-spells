import os
import pytest
from fastapi.testclient import TestClient

# Must mock dependencies before importing app
os.environ["AI_PROVIDER"] = "mock"

from app.main import app, get_provider
from app.providers import AIProvider, MockProvider, ProviderResult, ProviderStatus

_TINY_PNG_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# A custom DI mock provider to test dependency injection
class CustomTestProvider(AIProvider):
    async def submit(self, image_bytes, file_id, aspect_ratio="16:9", env=None, original_direction=None):
        return "custom-test-task", original_direction
    
    async def check_status(self, provider_task_id, env=None):
        return ProviderResult(status=ProviderStatus.COMPLETED, video_url="https://test.video", facing_direction="left")

def override_get_provider():
    return CustomTestProvider()

def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

def test_upload_artwork_with_di_override():
    # Override the DI provider for this test
    app.dependency_overrides[get_provider] = override_get_provider
    try:
        with TestClient(app) as client:
            response = client.post("/api/upload", json={"image_data": _TINY_PNG_B64, "aspect_ratio": "16:9", "original_direction": "left", "room_id": "default"})
            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "generating"
            
            # Since CustomTestProvider returns "completed" instantly, we can check gallery
            gallery_res = client.get("/api/gallery")
            assert gallery_res.status_code == 200
            items = gallery_res.json()
            
            our_item = next((item for item in items if item["id"] == data["task_id"]), None)
            assert our_item is not None
            assert our_item["video_url"] == "https://test.video"
            assert our_item["facing_direction"] == "left"
    finally:
        # Reset override
        app.dependency_overrides.clear()
