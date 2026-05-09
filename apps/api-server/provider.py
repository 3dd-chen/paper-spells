"""
AI Provider abstraction layer.

Swap MockProvider for a real provider (e.g. RunwayProvider) when ready.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import uuid


class ProviderStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProviderResult:
    status: ProviderStatus
    video_url: Optional[str] = None
    error: Optional[str] = None


class AIProvider(ABC):
    """Abstract base class for AI video generation providers."""

    @abstractmethod
    async def submit(self, image_path: str) -> str:
        """Submit an image for video generation. Returns provider_task_id."""

    @abstractmethod
    async def check_status(self, provider_task_id: str) -> ProviderResult:
        """Check the status of a submitted task."""


class MockProvider(AIProvider):
    """
    Mock provider that immediately returns completed.
    Useful for local development and testing.
    """

    async def submit(self, image_path: str) -> str:
        return f"mock-{uuid.uuid4()}"

    async def check_status(self, provider_task_id: str) -> ProviderResult:
        return ProviderResult(
            status=ProviderStatus.COMPLETED,
            video_url=f"https://mock-storage.com/videos/{provider_task_id}.mp4",
        )
