from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.config import settings
from app.core.logging import app_logger
from app.db.session import get_db
from app.db.models import User
from app.schemas.image import (
    ImageUploadResponse, BatchUploadResponse, StorageType, 
    ImageCreate
)
from app.services.auth import get_current_active_user
from app.services.file import (
    validate_image_file, create_image_record, 
    create_upload_session, update_upload_session
)
from app.services.seaweedfs import upload_image_to_seaweedfs
from app.services.s3 import upload_image_to_s3
from app.services.image_processor import create_thumbnails, process_image

# Tạo router
router = APIRouter()


@router.post("/image", response_model=ImageUploadResponse)
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    storage_type: StorageType = Form(StorageType.LOCAL),
    create_thumb: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload một ảnh
    """
    # Kiểm tra file có hợp lệ không
    if not validate_image_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )
    
    # Tạo bản ghi Image
    image_in = ImageCreate(description=description)
    db_image = create_image_record(db, file, current_user.id, storage_type, description)
    
    # Upload lên storage tương ứng
    if storage_type == StorageType.SEAWEEDFS:
        db_image = upload_image_to_seaweedfs(db, db_image.id, file)
    elif storage_type == StorageType.S3:
        db_image = upload_image_to_s3(db, db_image.id, file)
    
    # Tạo thumbnails nếu cần
    if create_thumb:
        background_tasks.add_task(create_thumbnails, db, db_image.id)
    
    app_logger.info(f"Uploaded image: {db_image.id}, storage: {storage_type}")
    return {"image": db_image}


@router.post("/images", response_model=BatchUploadResponse)
async def upload_multiple_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    storage_type: StorageType = Form(StorageType.LOCAL),
    create_thumb: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload nhiều ảnh cùng lúc
    """
    # Tạo phiên upload
    upload_session = create_upload_session(db, current_user.id, len(files))
    
    uploaded_images = []
    failed_files = []
    processed_count = 0
    
    # Xử lý từng file
    for file in files:
        try:
            # Kiểm tra file có hợp lệ không
            if not validate_image_file(file):
                failed_files.append(file.filename)
                continue
            
            # Tạo bản ghi Image
            db_image = create_image_record(
                db, file, current_user.id, storage_type, description, upload_session.id
            )
            
            # Upload lên storage tương ứng
            if storage_type == StorageType.SEAWEEDFS:
                db_image = upload_image_to_seaweedfs(db, db_image.id, file)
            elif storage_type == StorageType.S3:
                db_image = upload_image_to_s3(db, db_image.id, file)
            
            # Tạo thumbnails nếu cần (trong background)
            if create_thumb:
                background_tasks.add_task(create_thumbnails, db, db_image.id)
            
            uploaded_images.append(db_image)
            processed_count += 1
            
            # Cập nhật trạng thái phiên upload
            update_upload_session(db, upload_session.id, processed_count)
            
        except Exception as e:
            app_logger.error(f"Error uploading file {file.filename}: {e}")
            failed_files.append(file.filename)
    
    # Cập nhật trạng thái phiên upload
    upload_session = update_upload_session(db, upload_session.id, processed_count)
    
    app_logger.info(f"Batch upload completed: {processed_count} files, {len(failed_files)} failed")
    return {
        "upload_session": upload_session,
        "uploaded_count": len(uploaded_images),
        "failed_count": len(failed_files),
        "images": uploaded_images,
        "failed_files": failed_files,
    }


@router.post("/seaweedfs", response_model=ImageUploadResponse)
async def upload_to_seaweedfs(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    create_thumb: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload ảnh lên SeaweedFS
    """
    # Kiểm tra file có hợp lệ không
    if not validate_image_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )
    
    # Tạo bản ghi Image
    db_image = create_image_record(db, file, current_user.id, StorageType.SEAWEEDFS, description)
    
    file.file.seek(0)

    # Upload lên SeaweedFS
    db_image = upload_image_to_seaweedfs(db, db_image.id, file)
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading to SeaweedFS",
        )
    
    # Tạo thumbnails nếu cần
    if create_thumb:
        background_tasks.add_task(create_thumbnails, db, db_image.id)
    
    app_logger.info(f"Uploaded image to SeaweedFS: {db_image.id}")
    return {"image": db_image}


@router.post("/s3", response_model=ImageUploadResponse)
async def upload_to_s3(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    create_thumb: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload ảnh lên S3 (LocalStack)
    """
    # Kiểm tra file có hợp lệ không
    if not validate_image_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )
    
    # Tạo bản ghi Image
    db_image = create_image_record(db, file, current_user.id, StorageType.S3, description)
    
    # Upload lên S3
    db_image = upload_image_to_s3(db, db_image.id, file)
    if not db_image:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading to S3",
        )
    
    # Tạo thumbnails nếu cần
    if create_thumb:
        background_tasks.add_task(create_thumbnails, db, db_image.id)
    
    app_logger.info(f"Uploaded image to S3: {db_image.id}")
    return {"image": db_image}