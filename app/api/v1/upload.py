from typing import List, Optional

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, UploadFile, status)
from sqlalchemy.orm import Session

from app.core.logging import app_logger
from app.db.models import User
from app.db.session import get_db
from app.schemas.image import BatchUploadResponse
from app.schemas.image import Image as ImageSchema
from app.schemas.image import ImageUploadResponse, StorageType
from app.services.auth import get_current_active_user
from app.services.file import (create_image_record, create_upload_session,
                               update_upload_session, validate_image_file)
from app.services.image_processor import create_thumbnails
from app.services.s3 import upload_image_to_s3
from app.services.seaweedfs import upload_image_to_seaweedfs

# Create router
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
) -> ImageUploadResponse:
    """
    Upload a single image
    """
    if not validate_image_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )

    db_image = create_image_record(db, file, current_user.id, storage_type, description)

    if storage_type == StorageType.SEAWEEDFS:
        uploaded = upload_image_to_seaweedfs(db, db_image.id, file)
        if not uploaded:
            raise HTTPException(status_code=500, detail="Error uploading to SeaweedFS")
        db_image = uploaded
    elif storage_type == StorageType.S3:
        uploaded = upload_image_to_s3(db, db_image.id, file)
        if not uploaded:
            raise HTTPException(status_code=500, detail="Error uploading to S3")
        db_image = uploaded

    if create_thumb:
        background_tasks.add_task(create_thumbnails, db, db_image.id)

    app_logger.info(f"Uploaded image: {db_image.id}, storage: {storage_type}")
    return ImageUploadResponse(image=db_image)


@router.post("/images", response_model=BatchUploadResponse)
async def upload_multiple_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    storage_type: StorageType = Form(StorageType.LOCAL),
    create_thumb: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchUploadResponse:
    """
    Upload multiple images in a batch
    """
    upload_session = create_upload_session(db, current_user.id, len(files))
    uploaded_images = []
    failed_files = []
    processed_count = 0

    for file in files:
        try:
            if not validate_image_file(file):
                failed_files.append(file.filename)
                continue

            db_image = create_image_record(
                db, file, current_user.id, storage_type, description, upload_session.id
            )

            if storage_type == StorageType.SEAWEEDFS:
                uploaded = upload_image_to_seaweedfs(db, db_image.id, file)
                if not uploaded:
                    failed_files.append(file.filename)
                    continue
                db_image = uploaded
            elif storage_type == StorageType.S3:
                uploaded = upload_image_to_s3(db, db_image.id, file)
                if not uploaded:
                    failed_files.append(file.filename)
                    continue
                db_image = uploaded

            if create_thumb:
                background_tasks.add_task(create_thumbnails, db, db_image.id)

            uploaded_images.append(db_image)
            processed_count += 1
            update_upload_session(db, upload_session.id, processed_count)

        except Exception as e:
            app_logger.error(f"Error uploading file {file.filename}: {e}")
            failed_files.append(file.filename)

    upload_session = update_upload_session(db, upload_session.id, processed_count)

    app_logger.info(
        f"Batch upload completed: {processed_count} files, {len(failed_files)} failed"
    )
    return BatchUploadResponse(
        upload_session=upload_session,
        uploaded_count=len(uploaded_images),
        failed_count=len(failed_files),
        images=[ImageSchema.from_orm(img) for img in uploaded_images],
        failed_files=[f or "unknown" for f in failed_files],
    )


@router.post("/seaweedfs", response_model=ImageUploadResponse)
async def upload_to_seaweedfs(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    create_thumb: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImageUploadResponse:
    """
    Upload image to SeaweedFS
    """
    if not validate_image_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )

    db_image = create_image_record(
        db, file, current_user.id, StorageType.SEAWEEDFS, description
    )
    file.file.seek(0)

    uploaded = upload_image_to_seaweedfs(db, db_image.id, file)
    if not uploaded:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading to SeaweedFS",
        )
    db_image = uploaded

    if create_thumb:
        background_tasks.add_task(create_thumbnails, db, db_image.id)

    app_logger.info(f"Uploaded image to SeaweedFS: {db_image.id}")
    return ImageUploadResponse(image=db_image)


@router.post("/s3", response_model=ImageUploadResponse)
async def upload_to_s3(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    create_thumb: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImageUploadResponse:
    """
    Upload image to S3 (e.g., LocalStack)
    """
    if not validate_image_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )

    db_image = create_image_record(
        db, file, current_user.id, StorageType.S3, description
    )

    uploaded = upload_image_to_s3(db, db_image.id, file)
    if not uploaded:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading to S3",
        )
    db_image = uploaded

    if create_thumb:
        background_tasks.add_task(create_thumbnails, db, db_image.id)

    app_logger.info(f"Uploaded image to S3: {db_image.id}")
    return ImageUploadResponse(image=db_image)
