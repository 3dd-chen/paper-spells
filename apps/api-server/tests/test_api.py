import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

# Must mock dependencies before importing app
os.environ["AI_PROVIDER"] = "mock"

from main import app
from app.dependencies import get_provider, get_repo
from app.providers import AIProvider, MockProvider, ProviderResult, ProviderStatus
from app.db.repository import ArtworkRepository

_TINY_PNG_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# ── Mock D1 Database ──────────────────────────────────────────────────────────

class MockD1Results:
    def __init__(self, rows):
        self.rows = rows
    def to_py(self):
        return self.rows

class MockD1Result:
    def __init__(self, rows):
        self.results = MockD1Results(rows)

class MockD1Statement:
    def __init__(self, conn, sql):
        self.conn = conn
        self.sql = sql
        self.args = []

    def bind(self, *args):
        self.args = list(args)
        return self

    async def run(self):
        cursor = self.conn.cursor()
        cursor.execute(self.sql, self.args)
        self.conn.commit()
        return MockD1Result([])

    async def all(self):
        cursor = self.conn.cursor()
        cursor.execute(self.sql, self.args)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return MockD1Result(rows)
class MockD1Database:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.execute("""
        CREATE TABLE artworks (
            id TEXT PRIMARY KEY,
            image_path TEXT,
            helmet_image_path TEXT,
            video_url TEXT,
            status TEXT DEFAULT 'pending',
            provider_task_id TEXT,
            facing_direction TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            room_id TEXT NOT NULL DEFAULT 'default',
            hidden INTEGER DEFAULT 0
        )""")
        self.conn.commit()

    def prepare(self, sql):
        return MockD1Statement(self.conn, sql)


mock_db = MockD1Database()

async def override_get_repo():
    return ArtworkRepository(mock_db)


# ── Custom AI Provider Mock ──────────────────────────────────────────────────

class CustomTestProvider(AIProvider):
    async def submit(self, image_bytes, file_id, aspect_ratio="16:9", env=None, original_direction=None, character_description=None):
        return "custom-test-task", original_direction, "https://test.video_helmet.png"
    
    async def check_status(self, provider_task_id, env=None):
        return ProviderResult(status=ProviderStatus.COMPLETED, video_url="https://test.video", facing_direction="left")

def override_get_provider():
    return CustomTestProvider()


# ── Tests ────────────────────────────────────────────────────────────────────

def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

def test_upload_artwork_with_di_override():
    # Override dependencies
    app.dependency_overrides[get_provider] = override_get_provider
    app.dependency_overrides[get_repo] = override_get_repo
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/upload",
                json={
                    "image_data": _TINY_PNG_B64,
                    "aspect_ratio": "16:9",
                    "original_direction": "left",
                    "room_id": "default"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "generating"
            # Call poll endpoint to trigger task status transition from generating to completed
            poll_response = client.post("/api/poll?room_id=default")
            assert poll_response.status_code == 200

            # Since CustomTestProvider returns "completed" instantly, we can check gallery
            gallery_res = client.get("/api/gallery")
            assert gallery_res.status_code == 200
            items = gallery_res.json()
            
            our_item = next((item for item in items if item["id"] == data["task_id"]), None)
            assert our_item is not None
            assert our_item["video_url"] == "https://test.video"
            assert our_item["facing_direction"] == "left"
    finally:
        app.dependency_overrides.clear()
