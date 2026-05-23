"""
Abstract base class and shared types for AI video generation providers.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any


class ProviderStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProviderResult:
    status: ProviderStatus
    video_url: Optional[str] = None
    error: Optional[str] = None
    facing_direction: Optional[str] = None


class AIProvider(ABC):
    """Abstract base class for AI video generation providers."""

    @abstractmethod
    async def submit(self, image_bytes: bytes, file_id: str, aspect_ratio: str = "16:9", env: Any = None, original_direction: str | None = None) -> tuple[str, str | None]:
        """
        Submits an image for video generation.
        Returns a tuple: (task_id, original_direction)
        """

    @abstractmethod
    async def check_status(self, provider_task_id: str, env: Any = None) -> ProviderResult:
        """Check the status of a previously submitted task."""
