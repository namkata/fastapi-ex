import os
from typing import BinaryIO, Optional

from fastapi import UploadFile
from pyseaweed import SeaweedFS
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image
from app.schemas.image import StorageType


class SeaweedFSService:
    def __init__(self) -> None:
        try:
            self.seaweed = SeaweedFS(
                master_addr=settings.SEAWEEDFS_MASTER_URL.split("://")[-1].split(":")[
                    0
                ],
                master_port=int(settings.SEAWEEDFS_MASTER_URL.split(":")[-1]),
            )
            self.available = True
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Initialization error: {e}")
            self.available = False

    def upload_file(self, file: BinaryIO, filename: str) -> Optional[str]:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            file.seek(0)
            fid = self.seaweed.upload_file(stream=file, name=filename)
            app_logger.info(f"[SeaweedFS] Uploaded: {fid}")
            return fid
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload error: {e}")
            return None

    def upload_from_path(self, file_path: str) -> Optional[str]:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            with open(file_path, "rb") as f:
                return self.upload_file(f, os.path.basename(file_path))
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload from path error: {e}")
            return None

    def upload_from_upload_file(self, upload_file: UploadFile) -> Optional[str]:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            filename = upload_file.filename or ""
            return self.upload_file(upload_file.file, filename)
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload from UploadFile error: {e}")
            return None

    def get_file_url(self, fid: str) -> Optional[str]:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            return self.seaweed.get_file_url(fid)
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Get URL error: {e}")
            return None

    def delete_file(self, fid: str) -> bool:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return False
        try:
            result = self.seaweed.delete_file(fid)
            app_logger.info(f"[SeaweedFS] Deleted: {fid}")
            return result
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Delete error: {e}")
            return False

    def download_file(self, fid: str) -> Optional[bytes]:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            return self.seaweed.get_file(fid)
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Download error: {e}")
            return None


# Init SeaWeedFS Service
seaweedfs_service = SeaweedFSService()


def update_image_record(db: Session, db_image: Image, fid: str, url: str) -> Image:
    db_image.storage_type = StorageType.SEAWEEDFS.value
    db_image.seaweedfs_fid = fid
    db_image.storage_path = url

    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


def upload_image_to_seaweedfs(
    db: Session, image_id: int, file: UploadFile
) -> Optional[Image]:
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"[SeaweedFS] Image not found: {image_id}")
        return None

    fid = seaweedfs_service.upload_from_upload_file(file)
    if not fid:
        app_logger.error(f"[SeaweedFS] Upload failed: {image_id}")
        return None

    url = seaweedfs_service.get_file_url(fid)
    if not url:
        app_logger.error(f"[SeaweedFS] Cannot get URL for FID: {fid}")
        return None

    updated = update_image_record(db, db_image, fid, url)
    app_logger.info(f"[SeaweedFS] Uploaded image: {image_id}, fid: {fid}")
    return updated


def upload_local_image_to_seaweedfs(db: Session, image_id: int) -> Optional[Image]:
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"[SeaweedFS] Image not found: {image_id}")
        return None

    file_path = str(db_image.file_path or "")
    if not file_path or not os.path.exists(file_path):
        app_logger.error(f"[SeaweedFS] File does not exist: {file_path}")
        return None

    fid = seaweedfs_service.upload_from_path(file_path)
    if not fid:
        app_logger.error(f"[SeaweedFS] Upload failed from path: {image_id}")
        return None

    url = seaweedfs_service.get_file_url(fid)
    if not url:
        app_logger.error(f"[SeaweedFS] Cannot get URL for FID: {fid}")
        return None

    updated = update_image_record(db, db_image, fid, url)
    app_logger.info(f"[SeaweedFS] Uploaded local image: {image_id}, fid: {fid}")
    return updated


def delete_image_from_seaweedfs(db: Session, image_id: int) -> bool:
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"[SeaweedFS] Image not found: {image_id}")
        return False

    if (
        db_image.storage_type != StorageType.SEAWEEDFS.value
        or not db_image.seaweedfs_fid
    ):
        app_logger.error(f"[SeaweedFS] Image not stored on SeaweedFS: {image_id}")
        return False

    result = seaweedfs_service.delete_file(str(db_image.seaweedfs_fid))
    if not result:
        app_logger.error(f"[SeaweedFS] Delete failed: {image_id}")
        return False

    app_logger.info(f"[SeaweedFS] Deleted image: {image_id}")
    return True
