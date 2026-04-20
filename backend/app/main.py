from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1.router import api_router
from app.api.v1.oidc import router as oidc_router, discovery_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Система управления доступом с многофакторной аутентификацией",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Internal IAM API (versioned)
app.include_router(api_router, prefix="/api")

# OIDC / OAuth 2.0 endpoints (top-level, no version prefix)
app.include_router(oidc_router, prefix="/oauth", tags=["OIDC"])
app.include_router(discovery_router, prefix="/.well-known", tags=["OIDC Discovery"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
