"""
Pydantic request/response schemas for the Paper Spells API.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class UploadRequest(BaseModel):
    image_data: str          # Base64-encoded image (with or without data-URI prefix)
    aspect_ratio: Optional[str] = "16:9"


class UploadResponse(BaseModel):
    task_id: str
    status: str


class GalleryItem(BaseModel):
    id: str
    video_url: Optional[str] = None
    image_path: Optional[str] = None
    facing_direction: Optional[str] = None
