from fastapi import APIRouter

from app.api.v1 import auth, images, upload, users

# Tạo API router
api_router = APIRouter()

# Đăng ký các endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
