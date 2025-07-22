import os
import uuid
from typing import BinaryIO, Optional

from fastapi import UploadFile
from pyseaweed import SeaweedFS
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image
from app.schemas.image import StorageType
from app.services.storage_manager import StorageBackend


class SeaweedFSService(StorageBackend):
    def _initialize(self) -> None:
        """Initialize SeaweedFS client"""
        try:
            # Parse master URL to extract host and port
            master_url = settings.SEAWEEDFS_MASTER_URL
            if "://" in master_url:
                master_url = master_url.split("://")[-1]
            
            if ":" in master_url:
                master_addr, master_port_str = master_url.rsplit(":", 1)
                master_port = int(master_port_str)
            else:
                master_addr = master_url
                master_port = 9333  # Default SeaweedFS master port
            
            self.seaweed = SeaweedFS(
                master_addr=master_addr,
                master_port=master_port,
            )
            
            # Test connection by getting cluster status
            import requests

            try:
                response = requests.get(f"http://{master_addr}:{master_port}/dir/status")
                if response.status_code == 200:
                    self.available = True
                    app_logger.info(f"SeaweedFS service initialized successfully (master: {master_addr}:{master_port})")
                else:
                    raise Exception(f"Unexpected status code: {response.status_code}")
            except Exception as test_e:
                app_logger.warning(f"SeaweedFS connection test failed, but service will be marked as available: {test_e}")
                self.available = True
                
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Initialization error: {e}")
            self.available = False

    def upload_file(self, file: BinaryIO, key: str, **kwargs) -> bool:
        """Upload file and store the FID in the key for later retrieval"""
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return False
        try:
            file.seek(0)
            # Extract filename from key for SeaweedFS
            filename = os.path.basename(key) if key else "unnamed_file"
            fid = self.seaweed.upload_file(stream=file, name=filename)
            
            if fid:
                # Store the FID mapping for later retrieval
                self._store_fid_mapping(key, fid)
                app_logger.info(f"[SeaweedFS] Uploaded: {key} -> {fid}")
                return True
            return False
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload error: {e}")
            return False
    
    def _store_fid_mapping(self, key: str, fid: str) -> None:
        """Store FID mapping (in a real implementation, this would be in a database)"""
        # For now, we'll store it in memory. In production, use a database.
        if not hasattr(self, '_fid_mappings'):
            self._fid_mappings = {}
        self._fid_mappings[key] = fid
    
    def _get_fid_from_key(self, key: str) -> Optional[str]:
         """Get FID from key mapping"""
         if not hasattr(self, '_fid_mappings'):
             return None
         return self._fid_mappings.get(key)

    def get_fid_for_key(self, key: str) -> Optional[str]:
        return self._get_fid_from_key(key)

    def file_exists(self, key: str) -> bool:
        """Check if file exists by key"""
        fid = self._get_fid_from_key(key)
        if not fid:
            return False
            
        # Try to get file info to check existence
        try:
            if not self.available:
                return False
            # SeaweedFS doesn't have a direct "exists" method, so we try to get file info
            result = self.download_file_by_fid(fid)
            return result is not None
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Error checking file existence: {e}")
            return False
    
    def upload_file_direct(self, file: BinaryIO, filename: str) -> Optional[str]:
        """Direct upload that returns FID (for backward compatibility)"""
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

    def upload_from_path(self, file_path: str, key: Optional[str] = None, **kwargs) -> bool:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return False
        try:
            if not os.path.exists(file_path):
                app_logger.error(f"[SeaweedFS] File not found: {file_path}")
                return False
            
            if key is None:
                filename = os.path.basename(file_path)
                ext = os.path.splitext(filename)[-1].lower()
                key = f"uploads/{uuid.uuid4().hex}{ext}"
            
            with open(file_path, "rb") as f:
                return self.upload_file(f, key, **kwargs)
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload from path error: {e}")
            return False
    
    def upload_from_path_direct(self, file_path: str) -> Optional[str]:
        """Direct upload from path that returns FID (for backward compatibility)"""
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            with open(file_path, "rb") as f:
                return self.upload_file_direct(f, os.path.basename(file_path))
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload from path error: {e}")
            return None

    def upload_from_upload_file(self, upload_file: UploadFile, key: Optional[str] = None, **kwargs) -> bool:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return False
        try:
            filename = upload_file.filename or "unnamed_file"
            if key is None:
                ext = os.path.splitext(filename)[-1].lower()
                key = f"uploads/{uuid.uuid4().hex}{ext}"
            
            upload_file.file.seek(0)  # Ensure we're at the beginning
            return self.upload_file(upload_file.file, key, **kwargs)
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload from UploadFile error: {e}")
            return False
    
    def upload_from_upload_file_direct(self, upload_file: UploadFile) -> Optional[str]:
        """Direct upload from UploadFile that returns FID (for backward compatibility)"""
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            filename = upload_file.filename or ""
            return self.upload_file_direct(upload_file.file, filename)
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Upload from UploadFile error: {e}")
            return None

    def get_file_url(self, key: str) -> Optional[str]:
        """Get file URL from key"""
        fid = self._get_fid_from_key(key)
        if not fid:
            app_logger.error(f"[SeaweedFS] No FID found for key: {key}")
            return None
        return self.get_file_url_from_fid(fid)
    
    def get_file_url_from_fid(self, fid: str) -> Optional[str]:
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            # Parse the FID to extract volume ID and file key
            # FID format is typically: volume_id,file_key
            if ',' not in fid:
                app_logger.error(f"[SeaweedFS] Invalid FID format: {fid}")
                return None
            
            volume_id, file_key = fid.split(',', 1)
            
            # Construct URL using the configured volume server URL instead of volume name
            volume_url = settings.SEAWEEDFS_VOLUME_URL.rstrip('/')
            file_url = f"{volume_url}/{volume_id}/{file_key}"
            
            app_logger.info(f"[SeaweedFS] Generated URL: {file_url}")
            return file_url
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Get URL error: {e}")
            return None

    def get_file_url_with_custom_volume_server(self, fid: str, volume_server_url: str) -> Optional[str]:
        """
        Get file URL using a custom volume server URL (IP or domain)
        
        Args:
            fid: File ID in format volume_id,file_key
            volume_server_url: Custom volume server URL (e.g., http://192.168.1.100:8080)
        
        Returns:
            Complete file URL or None if error
        """
        if not self.available:
            app_logger.warning("[SeaweedFS] Service unavailable.")
            return None
        try:
            # Parse the FID to extract volume ID and file key
            if ',' not in fid:
                app_logger.error(f"[SeaweedFS] Invalid FID format: {fid}")
                return None
            
            volume_id, file_key = fid.split(',', 1)
            
            # Construct URL using the provided volume server URL
            volume_url = volume_server_url.rstrip('/')
            file_url = f"{volume_url}/{volume_id}/{file_key}"
            
            app_logger.info(f"[SeaweedFS] Generated custom URL: {file_url}")
            return file_url
        except Exception as e:
            app_logger.error(f"[SeaweedFS] Get custom URL error: {e}")
            return None

    def delete_file(self, key: str) -> bool:
        """Delete file by key"""
        fid = self._get_fid_from_key(key)
        if not fid:
            app_logger.error(f"[SeaweedFS] No FID found for key: {key}")
            return False
        
        result = self.delete_file_by_fid(fid)
        if result:
            # Remove from mapping
            if hasattr(self, '_fid_mappings') and key in self._fid_mappings:
                del self._fid_mappings[key]
        return result
    
    def delete_file_by_fid(self, fid: str) -> bool:
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

    def download_file(self, key: str) -> Optional[bytes]:
        """Download file by key"""
        fid = self._get_fid_from_key(key)
        if not fid:
            app_logger.error(f"[SeaweedFS] No FID found for key: {key}")
            return None
        return self.download_file_by_fid(fid)
    
    def download_file_by_fid(self, fid: str) -> Optional[bytes]:
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
