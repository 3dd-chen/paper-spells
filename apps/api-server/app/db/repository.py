from __future__ import annotations
from typing import List, Optional
import uuid


class ArtworkRepository:
    def __init__(self, db):
        self.db = db

    async def create_artwork(self, image_path: str) -> dict:
        task_id = str(uuid.uuid4())
        await self.db.prepare(
            "INSERT INTO artworks (id, image_path, status) VALUES (?, ?, ?)"
        ).bind(task_id, image_path, "pending").run()
        
        return {
            "id": task_id,
            "image_path": image_path,
            "status": "pending"
        }

    async def get_by_id(self, task_id: str) -> Optional[dict]:
        result = await self.db.prepare("SELECT * FROM artworks WHERE id = ?").bind(task_id).all()
        items = result.results.to_py()
        return items[0] if items else None

    async def update_to_generating(self, task_id: str, provider_task_id: str, facing_direction: Optional[str] = None) -> bool:
        if facing_direction:
            await self.db.prepare(
                "UPDATE artworks SET status = ?, provider_task_id = ?, facing_direction = ? WHERE id = ?"
            ).bind("generating", provider_task_id, facing_direction, task_id).run()
        else:
            await self.db.prepare(
                "UPDATE artworks SET status = ?, provider_task_id = ? WHERE id = ?"
            ).bind("generating", provider_task_id, task_id).run()
        return True

    async def update_to_completed(self, task_id: str, video_url: str) -> bool:
        await self.db.prepare(
            "UPDATE artworks SET status = ?, video_url = ? WHERE id = ?"
        ).bind("completed", video_url, task_id).run()
        return True

    async def update_to_failed(self, task_id: str) -> bool:
        await self.db.prepare(
            "UPDATE artworks SET status = ? WHERE id = ?"
        ).bind("failed", task_id).run()
        return True

    async def get_all_generating(self) -> List[dict]:
        result = await self.db.prepare("SELECT * FROM artworks WHERE status = 'generating'").all()
        return result.results.to_py()

    async def get_all_completed(self) -> List[dict]:
        result = await self.db.prepare("SELECT * FROM artworks WHERE status = 'completed' ORDER BY created_at DESC").all()
        return result.results.to_py()
