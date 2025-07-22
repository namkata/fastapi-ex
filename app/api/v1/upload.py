from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.logging import app_logger
from app.db.models import User
from app.db.session import get_db
from app.schemas.image import BatchUploadResponse
from app.schemas.image import Image as ImageSchema
from app.schemas.image import ImageUploadResponse, StorageType
from app.services.auth import get_current_active_user
from app.services.file import (
    create_upload_session,
    update_upload_session,
)
from app.services.image_processor import create_thumbnails
from app.services.upload_service import upload_service
from app.services.storage_init import get_storage_health_report

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
    Upload a single image using the unified upload service
    """
    try:
        db_image = await upload_service.upload_file(
            db=db,
            file=file,
            user_id=current_user.id,
            storage_type=storage_type,
            description=description
        )
        
        if create_thumb:
            background_tasks.add_task(create_thumbnails, db, db_image.id)
        
        app_logger.info(f"Uploaded image: {db_image.id}, storage: {storage_type}")
        return ImageUploadResponse(image=db_image)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        app_logger.error(f"Error uploading image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading image"
        )


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
    Upload multiple images in a batch using the unified upload service
    """
    upload_session = create_upload_session(db, current_user.id, len(files))
    
    try:
        result = await upload_service.batch_upload(
            db=db,
            files=files,
            user_id=current_user.id,
            storage_type=storage_type,
            description=description,
            upload_session_id=upload_session.id
        )
        
        # Add thumbnail creation tasks for successful uploads
        if create_thumb:
            for image in result["uploaded_images"]:
                background_tasks.add_task(create_thumbnails, db, image.id)
        
        # Update final session status
        upload_session = update_upload_session(db, upload_session.id, result["uploaded_count"])
        
        app_logger.info(
            f"Batch upload completed: {result['uploaded_count']} files, {result['failed_count']} failed"
        )
        
        return BatchUploadResponse(
            upload_session=upload_session,
            uploaded_count=result["uploaded_count"],
            failed_count=result["failed_count"],
            images=[ImageSchema.from_orm(img) for img in result["uploaded_images"]],
            failed_files=result["failed_files"],
        )
        
    except Exception as e:
        app_logger.error(f"Error in batch upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing batch upload"
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
    Upload image directly to SeaweedFS using the unified upload service
    """
    try:
        db_image = await upload_service.upload_file(
            db=db,
            file=file,
            user_id=current_user.id,
            storage_type=StorageType.SEAWEEDFS,
            description=description
        )
        
        if create_thumb:
            background_tasks.add_task(create_thumbnails, db, db_image.id)
        
        app_logger.info(f"Uploaded image to SeaweedFS: {db_image.id}")
        return ImageUploadResponse(image=db_image)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        app_logger.error(f"Error uploading to SeaweedFS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading to SeaweedFS"
        )


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
    Upload image directly to S3 (e.g., LocalStack) using the unified upload service
    """
    try:
        db_image = await upload_service.upload_file(
            db=db,
            file=file,
            user_id=current_user.id,
            storage_type=StorageType.S3,
            description=description
        )
        
        if create_thumb:
            background_tasks.add_task(create_thumbnails, db, db_image.id)
        
        app_logger.info(f"Uploaded image to S3: {db_image.id}")
        return ImageUploadResponse(image=db_image)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        app_logger.error(f"Error uploading to S3: {e}")
        raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Error uploading to S3"
         )


@router.get("/health")
async def storage_health_check() -> dict:
    """
    Get health status of all storage backends
    """
    try:
        health_report = get_storage_health_report()
        return {
            "status": "ok" if health_report["available_count"] > 0 else "degraded",
            "storage_backends": health_report["backends"],
            "available_backends": health_report["available_count"],
            "total_backends": health_report["total_count"]
        }
    except Exception as e:
        app_logger.error(f"Error checking storage health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking storage health"
        )
