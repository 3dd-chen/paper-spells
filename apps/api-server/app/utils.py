"""
Utility helper functions for image parsing and processing.
"""
from __future__ import annotations

def get_png_ratio(data: bytes) -> str:
    """Helper to detect aspect ratio ("16:9" or "9:16") from PNG binary data headers."""
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 24:
        w = int.from_bytes(data[16:20], byteorder="big")
        h = int.from_bytes(data[20:24], byteorder="big")
        return "9:16" if h > w else "16:9"
    return "16:9"
