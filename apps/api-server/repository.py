from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Artwork

class ArtworkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_artwork(self) -> Artwork:
        artwork = Artwork(status="pending")
        self.session.add(artwork)
        await self.session.commit()
        await self.session.refresh(artwork)
        return artwork

    async def get_by_id(self, task_id: str) -> Artwork:
        result = await self.session.execute(select(Artwork).where(Artwork.id == task_id))
        return result.scalar_one_or_none()

    async def update_to_completed(self, task_id: str, video_url: str) -> Artwork:
        artwork = await self.get_by_id(task_id)
        if artwork:
            artwork.status = "completed"
            artwork.video_url = video_url
            self.session.add(artwork)
            await self.session.commit()
        return artwork

    async def get_latest_completed(self, limit: int = 100) -> list[Artwork]:
        result = await self.session.execute(select(Artwork).where(Artwork.status == "completed").limit(limit))
        return list(result.scalars().all())
