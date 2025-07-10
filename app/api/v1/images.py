from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.db.models import User
from app.schemas.image import (
    ImageList,
    ImageUpdate,
    ProcessingTaskCreate,
    ProcessingTask,
)
from app.schemas.image import Image as ImageSchema
from app.schemas.image import Thumbnail as ThumbnailSchema

from app.services.auth import get_current_active_user
from app.services.file import get_image, get_images, update_image, delete_image
from app.services.image_processor import process_image, create_thumbnails
from app.services.seaweedfs import delete_image_from_seaweedfs
from app.services.s3 import delete_image_from_s3

router = APIRouter()


@router.get("/", response_model=ImageList)
async def list_images(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImageList:
    """
    Get the current user's images with pagination.
    """
    images, total = get_images(db, skip=skip, limit=limit, user_id=current_user.id)
    pages = (total + limit - 1) // limit if limit > 0 else 1
    page = (skip // limit) + 1 if limit > 0 else 1
    return ImageList(
        images=[ImageSchema.from_orm(img) for img in images],
        total=total,
        page=page,
        size=limit,
        pages=pages,
    )


@router.get("/all", response_model=ImageList)
async def list_all_images(
    skip: int = 0,
    limit: int = 20,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImageList:
    """
    Get all images (admin only), optionally filter by user_id.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    images, total = get_images(db, skip=skip, limit=limit, user_id=user_id)
    pages = (total + limit - 1) // limit if limit > 0 else 1
    page = (skip // limit) + 1 if limit > 0 else 1
    return ImageList(
        images=[ImageSchema.from_orm(img) for img in images],
        total=total,
        page=page,
        size=limit,
        pages=pages,
    )


@router.get("/{image_id}", response_model=ImageSchema)
async def get_image_by_id(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImageSchema:
    """
    Get image details by ID (only owner or admin).
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return db_image


@router.put("/{image_id}", response_model=ImageSchema)
async def update_image_by_id(
    image_id: int,
    image_in: ImageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImageSchema:
    """
    Update image metadata (only owner or admin).
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    updated = update_image(db, image_id, image_in.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=500, detail="Error updating image")

    return updated


@router.delete("/{image_id}", response_model=ImageSchema)
async def delete_image_by_id(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImageSchema:
    """
    Delete image by ID (only owner or admin).
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if db_image.storage_type == "seaweedfs":
        delete_image_from_seaweedfs(db, image_id)
    elif db_image.storage_type == "s3":
        delete_image_from_s3(db, image_id)

    if not delete_image(db, image_id):
        raise HTTPException(status_code=500, detail="Error deleting image")

    return db_image


@router.post("/{image_id}/process", response_model=ProcessingTask)
async def create_processing_task(
    image_id: int,
    task_in: ProcessingTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProcessingTask:
    """
    Create a new processing task for the image.
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    from app.services.file import create_processing_task

    task = create_processing_task(db, image_id, task_in.task_type, task_in.params)

    # Normally should be done asynchronously
    process_image(db, task.id)
    db.refresh(task)

    return task


@router.post("/{image_id}/thumbnails", response_model=List[ThumbnailSchema])
async def generate_thumbnails(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[ThumbnailSchema]:
    """
    Generate thumbnails for the image.
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    if db_image.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    thumbnails = create_thumbnails(db, image_id)
    if not thumbnails:
        raise HTTPException(status_code=500, detail="Error creating thumbnails")

    return [ThumbnailSchema.from_orm(t) for t in thumbnails]
