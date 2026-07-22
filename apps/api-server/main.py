from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.logging import setup_logging, logger
from app.middleware import LoggingASGIMiddleware, DynamicCORSMiddleware
from app.routes import public_router, admin_router

# Initialize Python logging to forward records to Worker console
setup_logging()

app = FastAPI(
    title="Paper Spells API",
    description="Edge-native FastAPI backend running on Cloudflare Workers (Pyodide).",
    version="1.0.0"
)

# Register ASGI Middlewares
app.add_middleware(LoggingASGIMiddleware)
app.add_middleware(DynamicCORSMiddleware)

# Register Routers
app.include_router(public_router)
app.include_router(admin_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal error: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred."}
    )


# ── Cloudflare Workers Pyodide Entrypoint ─────────────────────────────────────
try:
    from workers import WorkerEntrypoint

    class Default(WorkerEntrypoint):
        async def fetch(self, request):
            import asgi
            return await asgi.fetch(app, request.js_object, self.env)
except ImportError:
    pass