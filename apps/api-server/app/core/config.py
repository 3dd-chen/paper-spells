from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class Settings:
    gcp_project_id: str
    gcp_service_account: str
    google_cloud_location: str
    ai_provider: str
    gemini_api_key: str | None
    veo_model_name: str
    gemini_model_name: str
    r2_public_url: str
    jwt_secret: str
    allowed_origins: list[str]
    
    @classmethod
    def from_env(cls, env: Any) -> Settings:
        origins_raw = getattr(env, "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173")
        allowed_origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
        return cls(
            gcp_project_id=getattr(env, "GCP_PROJECT_ID", "your-gcp-project-id"),
            gcp_service_account=getattr(env, "GCP_SERVICE_ACCOUNT", ""),
            google_cloud_location=getattr(env, "GOOGLE_CLOUD_LOCATION", "us-central1"),
            ai_provider=getattr(env, "AI_PROVIDER", "mock"),
            gemini_api_key=getattr(env, "GEMINI_API_KEY", None),
            veo_model_name=getattr(env, "VEO_MODEL_NAME", "veo-3.1-lite-generate-001"),
            gemini_model_name=getattr(env, "GEMINI_MODEL_NAME", "gemini-3.1-flash-lite"),
            r2_public_url=getattr(env, "R2_PUBLIC_URL", "https://media.yourdomain.com"),
            jwt_secret=getattr(env, "JWT_SECRET", "dev-secret-change-me"),
            allowed_origins=allowed_origins,
        )
