from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Artwork


class ArtworkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_artwork(self, image_path: str) -> Artwork:
        artwork = Artwork(status="pending", image_path=image_path)
        self.session.add(artwork)
        await self.session.commit()
        await self.session.refresh(artwork)
        return artwork

    async def get_by_id(self, task_id: str) -> Optional[Artwork]:
        result = await self.session.execute(select(Artwork).where(Artwork.id == task_id))
        return result.scalar_one_or_none()

    async def update_to_generating(self, task_id: str, provider_task_id: str, facing_direction: Optional[str] = None) -> Optional[Artwork]:
        artwork = await self.get_by_id(task_id)
        if artwork:
            artwork.status = "generating"
            artwork.provider_task_id = provider_task_id
            if facing_direction:
                artwork.facing_direction = facing_direction
            self.session.add(artwork)
            await self.session.commit()
        return artwork

    async def update_to_completed(self, task_id: str, video_url: str) -> Optional[Artwork]:
        artwork = await self.get_by_id(task_id)
        if artwork:
            artwork.status = "completed"
            artwork.video_url = video_url
            self.session.add(artwork)
            await self.session.commit()
        return artwork

    async def update_to_failed(self, task_id: str) -> Optional[Artwork]:
        artwork = await self.get_by_id(task_id)
        if artwork:
            artwork.status = "failed"
            self.session.add(artwork)
            await self.session.commit()
        return artwork

    async def get_all_generating(self) -> List[Artwork]:
        result = await self.session.execute(
            select(Artwork).where(Artwork.status == "generating")
        )
        return list(result.scalars().all())

    async def get_all_completed(self) -> List[Artwork]:
        result = await self.session.execute(
            select(Artwork)
            .where(Artwork.status == "completed")
            .order_by(Artwork.created_at.desc())
        )
        return list(result.scalars().all())
