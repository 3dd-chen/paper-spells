from __future__ import annotations
from fastapi import Request, Depends, HTTPException
from app.db.repository import ArtworkRepository, AdminRepository
from app.providers import AIProvider, MockProvider, GeminiVeoProvider
from app.core.config import Settings
from app.interfaces.storage import CloudflareR2Storage
from app.interfaces.http_client import JsFetchClient
from app.auth import verify_token


async def get_settings(request: Request) -> Settings:
    env = request.scope.get("env", None)
    return Settings.from_env(env)


async def get_repo(request: Request) -> ArtworkRepository:
    if "env" in request.scope and hasattr(request.scope["env"], "DB"):
        return ArtworkRepository(request.scope["env"].DB)
    raise HTTPException(status_code=500, detail="D1 database binding not available")


async def get_admin_repo(request: Request) -> AdminRepository:
    if "env" in request.scope and hasattr(request.scope["env"], "DB"):
        return AdminRepository(request.scope["env"].DB)
    raise HTTPException(status_code=500, detail="D1 database binding not available")


async def get_provider(request: Request, settings: Settings = Depends(get_settings)) -> AIProvider:
    env = request.scope.get("env", None)
    http_client = JsFetchClient()
    storage = CloudflareR2Storage(env.BUCKET) if env and hasattr(env, "BUCKET") else None

    if settings.ai_provider == "gemini":
        return GeminiVeoProvider(settings=settings, http_client=http_client, storage=storage)
    return MockProvider()


async def require_admin(request: Request, settings: Settings = Depends(get_settings)):
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return verify_token(token, settings.jwt_secret)
