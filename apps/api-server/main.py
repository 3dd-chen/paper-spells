import asyncio
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from database import engine, Base, get_db
from models import Artwork
from repository import ArtworkRepository

app = FastAPI(title="Paper Spells API")

# Setup DB on startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Pydantic Schemas
class UploadRequest(BaseModel):
    image_data: str

class UploadResponse(BaseModel):
    task_id: str
    status: str

class StatusResponse(BaseModel):
    id: str
    status: str
    video_url: str = None

def get_artwork_repo(db: AsyncSession = Depends(get_db)) -> ArtworkRepository:
    return ArtworkRepository(db)

# Mock AI Service
async def mock_ai_generation(task_id: str):
    """Mocks the AI generation process."""
    await asyncio.sleep(2) # Simulate processing time
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        repo = ArtworkRepository(session)
        await repo.update_to_completed(task_id, f"https://mock-storage.com/videos/{task_id}.mp4")

# API Endpoints
@app.post("/api/upload", response_model=UploadResponse)
async def upload_artwork(req: UploadRequest, background_tasks: BackgroundTasks, repo: ArtworkRepository = Depends(get_artwork_repo)):
    # 1. Create artwork record
    artwork = await repo.create_artwork()

    # 2. Trigger background task
    background_tasks.add_task(mock_ai_generation, artwork.id)

    return UploadResponse(task_id=artwork.id, status=artwork.status)

@app.get("/api/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str, repo: ArtworkRepository = Depends(get_artwork_repo)):
    artwork = await repo.get_by_id(task_id)
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")
    
    return StatusResponse(
        id=artwork.id, 
        status=artwork.status, 
        video_url=artwork.video_url
    )

@app.get("/api/gallery/latest")
async def get_gallery_latest(repo: ArtworkRepository = Depends(get_artwork_repo)):
    artworks = await repo.get_latest_completed()
    return [{"id": a.id, "video_url": a.video_url} for a in artworks]
