"""
Mock provider — returns immediately with a fake video URL.
Useful for local development and unit tests without GCP credentials.
"""
from __future__ import annotations
import uuid
from typing import Optional, Any
from app.providers.base import AIProvider, ProviderResult, ProviderStatus


class MockProvider(AIProvider):
    async def submit(self, image_bytes: bytes, file_id: str, aspect_ratio: str = "16:9", env: Any = None) -> tuple[str, Optional[str]]:
        return f"mock-{uuid.uuid4()}", "right"

    async def check_status(self, provider_task_id: str, env: Any = None) -> ProviderResult:
        return ProviderResult(
            status=ProviderStatus.COMPLETED,
            video_url=f"https://mock-storage.com/videos/{provider_task_id}.mp4",
        )
