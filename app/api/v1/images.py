from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.logging import app_logger
from app.db.session import get_db
from app.db.models import User, Image as ImageModel
from app.schemas.image import (
    Image, ImageList, ImageUpdate, ProcessingTaskCreate, 
    ProcessingTask, Thumbnail
)
from app.services.auth import get_current_active_user
from app.services.file import get_image, get_images, update_image, delete_image
from app.services.image_processor import process_image, create_thumbnails
from app.services.seaweedfs import delete_image_from_seaweedfs
from app.services.s3 import delete_image_from_s3

# Tạo router
router = APIRouter()


@router.get("/", response_model=ImageList)
async def list_images(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy danh sách ảnh của user hiện tại
    """
    images, total = get_images(db, skip=skip, limit=limit, user_id=current_user.id)
    
    # Tính toán số trang
    pages = (total + limit - 1) // limit if limit > 0 else 1
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return {
        "images": images,
        "total": total,
        "page": page,
        "size": limit,
        "pages": pages,
    }


@router.get("/all", response_model=ImageList)
async def list_all_images(
    skip: int = 0,
    limit: int = 20,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy danh sách tất cả ảnh (admin) hoặc lọc theo user_id
    """
    # Kiểm tra quyền admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    images, total = get_images(db, skip=skip, limit=limit, user_id=user_id)
    
    # Tính toán số trang
    pages = (total + limit - 1) // limit if limit > 0 else 1
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return {
        "images": images,
        "total": total,
        "page": page,
        "size": limit,
        "pages": pages,
    }


@router.get("/{image_id}", response_model=Image)
async def get_image_by_id(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy thông tin ảnh theo ID
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )
    
    # Kiểm tra quyền truy cập
    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    return db_image


@router.put("/{image_id}", response_model=Image)
async def update_image_by_id(
    image_id: int,
    image_in: ImageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cập nhật thông tin ảnh theo ID
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )
    
    # Kiểm tra quyền truy cập
    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Cập nhật thông tin
    db_image = update_image(db, image_id, image_in.dict(exclude_unset=True))
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating image",
        )
    
    return db_image


@router.delete("/{image_id}", response_model=Image)
async def delete_image_by_id(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Xóa ảnh theo ID
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )
    
    # Kiểm tra quyền truy cập
    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Xóa ảnh khỏi storage
    if db_image.storage_type == "seaweedfs":
        delete_image_from_seaweedfs(db, image_id)
    elif db_image.storage_type == "s3":
        delete_image_from_s3(db, image_id)
    
    # Xóa bản ghi
    success = delete_image(db, image_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting image",
        )
    
    return db_image


@router.post("/{image_id}/process", response_model=ProcessingTask)
async def create_processing_task(
    image_id: int,
    task_in: ProcessingTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Tạo task xử lý ảnh
    """
    # Kiểm tra ảnh có tồn tại không
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )
    
    # Kiểm tra quyền truy cập
    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Tạo task xử lý
    from app.services.file import create_processing_task
    task = create_processing_task(db, image_id, task_in.task_type, task_in.params)
    
    # Xử lý ảnh (trong thực tế nên đưa vào background task)
    process_image(db, task.id)
    
    # Refresh task để lấy thông tin mới nhất
    db.refresh(task)
    
    return task


@router.post("/{image_id}/thumbnails", response_model=List[Thumbnail])
async def generate_thumbnails(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Tạo thumbnails cho ảnh
    """
    # Kiểm tra ảnh có tồn tại không
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )
    
    # Kiểm tra quyền truy cập
    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Tạo thumbnails
    thumbnails = create_thumbnails(db, image_id)
    if not thumbnails:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating thumbnails",
        )
    
    return thumbnails