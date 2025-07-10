"""Main application entrypoint for FastAPI app."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import create_tables
from app.utils.middleware import LoggingMiddleware

# Setup logging
setup_logging()

# Create 'logs' directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Create 'uploads' directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Include API routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static directory to serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Create database tables on startup
@app.on_event("startup")
async def startup_event() -> None:
    """Run on application startup: initialize DB tables."""
    create_tables()


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify app is running."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
