import os
import io
from typing import Optional, Dict, Any, BinaryIO
from fastapi import UploadFile
from pyseaweed import SeaweedFS
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image
from app.schemas.image import StorageType


class SeaweedFSService:
    def __init__(self):
        try:
            self.seaweed = SeaweedFS(
                master_addr=settings.SEAWEEDFS_MASTER_URL.split('://')[-1].split(':')[0],
                master_port=int(settings.SEAWEEDFS_MASTER_URL.split(':')[-1]),
            )
            self.available = True
        except Exception as e:
            app_logger.error(f"Error initializing SeaweedFS service: {e}")
            self.available = False
    
    def upload_file(self, file: BinaryIO, filename: str) -> Optional[str]:
        """
        Upload file to SeaweedFS
        """
        if not self.available:
            app_logger.warning("SeaweedFS service is not available")
            return None
            
        try:
            # Upload file
            fid = self.seaweed.upload_file(file, filename)
            app_logger.info(f"Uploaded file to SeaweedFS: {fid}")
            return fid
        except Exception as e:
            app_logger.error(f"Error uploading file to SeaweedFS: {e}")
            return None
    
    def upload_from_path(self, file_path: str) -> Optional[str]:
        """
        Upload file from local path to SeaweedFS
        """
        if not self.available:
            app_logger.warning("SeaweedFS service is not available")
            return None
            
        try:
            with open(file_path, 'rb') as f:
                filename = os.path.basename(file_path)
                return self.upload_file(f, filename)
        except Exception as e:
            app_logger.error(f"Error uploading file from path to SeaweedFS: {e}")
            return None
    
    def upload_from_upload_file(self, upload_file: UploadFile) -> Optional[str]:
        """
        Upload UploadFile to SeaweedFS
        """
        if not self.available:
            app_logger.warning("SeaweedFS service is not available")
            return None
            
        try:
            # Read file content
            file_content = upload_file.file.read()
            upload_file.file.seek(0)  # Reset file position
            
            # Upload to SeaweedFS
            file_obj = io.BytesIO(file_content)
            return self.upload_file(file_obj, upload_file.filename)
        except Exception as e:
            app_logger.error(f"Error uploading UploadFile to SeaweedFS: {e}")
            return None
    
    def get_file_url(self, fid: str) -> Optional[str]:
        """
        Get file URL from SeaweedFS
        """
        if not self.available:
            app_logger.warning("SeaweedFS service is not available")
            return None
            
        try:
            return self.seaweed.get_file_url(fid)
        except Exception as e:
            app_logger.error(f"Error getting file URL from SeaweedFS: {e}")
            return None
    
    def delete_file(self, fid: str) -> bool:
        """
        Delete file from SeaweedFS
        """
        if not self.available:
            app_logger.warning("SeaweedFS service is not available")
            return False
            
        try:
            return self.seaweed.delete_file(fid)
        except Exception as e:
            app_logger.error(f"Error deleting file from SeaweedFS: {e}")
            return False
    
    def download_file(self, fid: str) -> Optional[bytes]:
        """
        Download file from SeaweedFS
        """
        if not self.available:
            app_logger.warning("SeaweedFS service is not available")
            return None
            
        try:
            return self.seaweed.get_file(fid)
        except Exception as e:
            app_logger.error(f"Error downloading file from SeaweedFS: {e}")
            return None


# Khởi tạo service
seaweedfs_service = SeaweedFSService()


def upload_image_to_seaweedfs(db: Session, image_id: int, file: UploadFile) -> Optional[Image]:
    """
    Upload ảnh lên SeaweedFS và cập nhật bản ghi Image
    """
    # Lấy thông tin ảnh
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return None
    
    # Upload lên SeaweedFS
    fid = seaweedfs_service.upload_from_upload_file(file)
    if not fid:
        app_logger.error(f"Failed to upload image to SeaweedFS: {image_id}")
        return None
    
    # Lấy URL
    url = seaweedfs_service.get_file_url(fid)
    
    # Cập nhật bản ghi Image
    db_image.storage_type = StorageType.SEAWEEDFS
    db_image.seaweedfs_fid = fid
    db_image.storage_path = url
    
    # Lưu vào database
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    app_logger.info(f"Uploaded image to SeaweedFS: {image_id}, fid: {fid}")
    return db_image


def upload_local_image_to_seaweedfs(db: Session, image_id: int) -> Optional[Image]:
    """
    Upload ảnh từ local lên SeaweedFS và cập nhật bản ghi Image
    """
    # Lấy thông tin ảnh
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return None
    
    # Kiểm tra file có tồn tại không
    if not db_image.file_path or not os.path.exists(db_image.file_path):
        app_logger.error(f"Image file not found: {db_image.file_path}")
        return None
    
    # Upload lên SeaweedFS
    fid = seaweedfs_service.upload_from_path(db_image.file_path)
    if not fid:
        app_logger.error(f"Failed to upload image to SeaweedFS: {image_id}")
        return None
    
    # Lấy URL
    url = seaweedfs_service.get_file_url(fid)
    
    # Cập nhật bản ghi Image
    db_image.storage_type = StorageType.SEAWEEDFS
    db_image.seaweedfs_fid = fid
    db_image.storage_path = url
    
    # Lưu vào database
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    app_logger.info(f"Uploaded local image to SeaweedFS: {image_id}, fid: {fid}")
    return db_image


def delete_image_from_seaweedfs(db: Session, image_id: int) -> bool:
    """
    Xóa ảnh khỏi SeaweedFS
    """
    # Lấy thông tin ảnh
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return False
    
    # Kiểm tra ảnh có lưu trên SeaweedFS không
    if db_image.storage_type != StorageType.SEAWEEDFS or not db_image.seaweedfs_fid:
        app_logger.error(f"Image not stored on SeaweedFS: {image_id}")
        return False
    
    # Xóa khỏi SeaweedFS
    result = seaweedfs_service.delete_file(db_image.seaweedfs_fid)
    if not result:
        app_logger.error(f"Failed to delete image from SeaweedFS: {image_id}")
        return False
    
    app_logger.info(f"Deleted image from SeaweedFS: {image_id}")
    return True