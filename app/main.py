from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import api_router
from app.db.session import create_tables
from app.utils.middleware import LoggingMiddleware

# Thiết lập logging
setup_logging()

# Tạo thư mục logs nếu chưa tồn tại
os.makedirs("logs", exist_ok=True)

# Tạo thư mục uploads nếu chưa tồn tại
os.makedirs("uploads", exist_ok=True)

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Thiết lập CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thêm middleware logging
app.add_middleware(LoggingMiddleware)

# Đăng ký router API
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount thư mục static để phục vụ file tĩnh
app.mount("/static", StaticFiles(directory="static"), name="static")

# Tạo bảng database khi khởi động
@app.on_event("startup")
async def startup_event():
    create_tables()

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)