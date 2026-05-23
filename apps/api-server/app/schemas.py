"""
Pydantic request/response schemas for the Paper Spells API.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class UploadRequest(BaseModel):
    room_id: str
    image_data: str          # Base64-encoded image (with or without data-URI prefix)
    aspect_ratio: Optional[str] = "16:9"
    original_direction: Optional[str] = None


class AnalyzeDirectionRequest(BaseModel):
    image_data: str


class AnalyzeDirectionResponse(BaseModel):
    direction: str



class UploadResponse(BaseModel):
    task_id: str
    status: str


class GalleryItem(BaseModel):
    id: str
    video_url: Optional[str] = None
    image_path: Optional[str] = None
    facing_direction: Optional[str] = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    expires_at: int


class AdminArtworkItem(BaseModel):
    id: str
    room_id: str
    status: str
    hidden: int = 0
    video_url: Optional[str] = None
    image_path: Optional[str] = None
    facing_direction: Optional[str] = None
    created_at: Optional[str] = None


class AdminRoomItem(BaseModel):
    room_id: str
    count: int
