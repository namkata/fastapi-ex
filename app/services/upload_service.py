import os
import uuid
from typing import Optional, Dict, Any, List
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image
from app.services.image_processor import create_thumbnails
from app.schemas.image import StorageType, ProcessStatus
from app.services.storage_manager import storage_manager
from app.services.file import get_image_info, validate_image_file, create_image_record, update_upload_session


class UploadService:
    """Unified upload service that handles file uploads across different storage backends"""
    
    def __init__(self):
        self.storage_manager = storage_manager
    
    def _generate_unique_key(self, filename: str, image_id: int, storage_type: StorageType) -> str:
        """Generate a unique key for file storage"""
        ext = os.path.splitext(filename)[-1].lower()
        unique_id = uuid.uuid4().hex
        
        # Create a structured key based on storage type
        if storage_type == StorageType.S3:
            return f"images/{image_id}_{unique_id}{ext}"
        elif storage_type == StorageType.SEAWEEDFS:
            return f"seaweed/{image_id}_{unique_id}{ext}"
        else:
            return f"uploads/{image_id}_{unique_id}{ext}"
    
    def _get_storage_backend_name(self, storage_type: StorageType) -> str:
        """Map storage type to backend name"""
        mapping = {
            StorageType.S3: "s3",
            StorageType.SEAWEEDFS: "seaweedfs",
            StorageType.LOCAL: "local"
        }
        return mapping.get(storage_type, "local")
    
    async def upload_file(
        self, 
        db: Session,
        file: UploadFile, 
        user_id: int, 
        storage_type: StorageType = StorageType.LOCAL,
        description: Optional[str] = None,
        upload_session_id: Optional[int] = None
    ) -> Image:
        """
        Upload a file to the specified storage backend and create database record
        
        Args:
            db: Database session
            file: FastAPI UploadFile object
            user_id: ID of the user uploading the file
            storage_type: Target storage type
            description: Optional file description
            upload_session_id: Optional upload session ID for batch uploads
        
        Returns:
            Image database record
        """
        # Validate file
        if not validate_image_file(file):
            raise ValueError("Invalid image file")
        
        # Create initial database record
        db_image = create_image_record(
            db=db, 
            file=file, 
            user_id=user_id, 
            storage_type=storage_type, 
            description=description,
            upload_session_id=upload_session_id
        )
        
        # For local storage, file is already saved by create_image_record
        if storage_type == StorageType.LOCAL:
            return db_image
        
        try:
            # Generate unique key for remote storage
            filename = file.filename or "unnamed_file"
            key = self._generate_unique_key(filename, db_image.id, storage_type)
            
            # Upload to storage backend
            backend_name = self._get_storage_backend_name(storage_type)
            
            # Reset file position before upload
            file.file.seek(0)
            
            success = self.storage_manager.upload_from_upload_file(
                upload_file=file,
                key=key,
                backend_name=backend_name
            )
            
            if not success:
                # Clean up database record if upload fails
                db.delete(db_image)
                db.commit()
                raise Exception(f"Failed to upload to {storage_type.value} storage")
            
            # Get file URL and update database record
            file_url = self.storage_manager.get_file_url(key, backend_name)
            
            # Update database record with remote storage info
            db_image.storage_type = storage_type.value
            db_image.storage_path = key
            if storage_type == StorageType.S3:
                db_image.s3_key = key
                db_image.s3_url = file_url
                app_logger.info(f"Updated s3_url for image {db_image.id}: {file_url}")
            elif storage_type == StorageType.SEAWEEDFS:
                fid = self.storage_manager.get_backend(backend_name).get_fid_for_key(key)
                if fid:
                    db_image.seaweedfs_fid = fid
                    db_image.storage_path = file_url
            db.commit()
            db.refresh(db_image)
            
            # Auto create thumbnails and update status
            try:
                db_image.process_status = ProcessStatus.PROCESSING
                db.commit()
                
                thumbnails = create_thumbnails(db, db_image.id)
                if thumbnails:
                    db_image.process_status = ProcessStatus.COMPLETED
                else:
                    db_image.process_status = ProcessStatus.FAILED
                    db_image.process_error = "Failed to create thumbnails"
                db.commit()
            except Exception as e:
                db_image.process_status = ProcessStatus.FAILED
                db_image.process_error = str(e)
                db.commit()
                app_logger.error(f"Auto thumbnail creation error: {e}")

            app_logger.info(f"Successfully uploaded file {filename} to {storage_type.value}")
            return db_image
        
        except Exception as e:
            app_logger.error(f"Upload service error: {e}")
            # Clean up database record if upload fails
            try:
                db.delete(db_image)
                db.commit()
            except:
                pass
            raise e
    
    def upload_from_path(
        self,
        file_path: str,
        user_id: int,
        storage_type: StorageType = StorageType.LOCAL,
        custom_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a file from local path to the specified storage backend
        """
        try:
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": "File not found",
                    "details": f"File does not exist: {file_path}"
                }
            
            # Generate unique key if not provided
            filename = os.path.basename(file_path)
            key = custom_key or self._generate_unique_key(filename, user_id, storage_type)
            
            # Prepare upload parameters
            upload_params = {}
            if metadata:
                upload_params['metadata'] = metadata
            
            # Upload to storage backend
            backend_name = self._get_storage_backend_name(storage_type)
            
            success = self.storage_manager.upload_from_path(
                file_path=file_path,
                key=key,
                backend_name=backend_name,
                **upload_params
            )
            
            if not success:
                return {
                    "success": False,
                    "error": "Upload failed",
                    "details": f"Failed to upload to {storage_type.value} storage"
                }
            
            # Get file URL
            file_url = self.storage_manager.get_file_url(key, backend_name)
            
            return {
                "success": True,
                "key": key,
                "url": file_url,
                "storage_type": storage_type.value,
                "backend": backend_name,
                "original_filename": filename
            }
            
        except Exception as e:
            app_logger.error(f"Upload from path error: {e}")
            return {
                "success": False,
                "error": "Internal error",
                "details": str(e)
            }
    
    def delete_file(
        self,
        key: str,
        storage_type: StorageType
    ) -> Dict[str, Any]:
        """
        Delete a file from the specified storage backend
        """
        try:
            backend_name = self._get_storage_backend_name(storage_type)
            
            success = self.storage_manager.delete_file(key, backend_name)
            
            return {
                "success": success,
                "key": key,
                "storage_type": storage_type.value,
                "backend": backend_name
            }
            
        except Exception as e:
            app_logger.error(f"Delete file error: {e}")
            return {
                "success": False,
                "error": "Internal error",
                "details": str(e)
            }
    
    def get_file_url(
        self,
        key: str,
        storage_type: StorageType
    ) -> Optional[str]:
        """
        Get file URL from the specified storage backend
        """
        try:
            backend_name = self._get_storage_backend_name(storage_type)
            return self.storage_manager.get_file_url(key, backend_name)
        except Exception as e:
            app_logger.error(f"Get file URL error: {e}")
            return None
    
    def file_exists(
        self,
        key: str,
        storage_type: StorageType
    ) -> bool:
        """
        Check if file exists in the specified storage backend
        """
        try:
            backend_name = self._get_storage_backend_name(storage_type)
            return self.storage_manager.file_exists(key, backend_name)
        except Exception as e:
            app_logger.error(f"File exists check error: {e}")
            return False
    
    def get_storage_health(self) -> Dict[str, Any]:
        """
        Get health status of all storage backends
        """
        return self.storage_manager.health_check()
    
    async def batch_upload(
        self,
        db: Session,
        files: List[UploadFile],
        user_id: int,
        storage_type: StorageType = StorageType.LOCAL,
        description: Optional[str] = None,
        upload_session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Upload multiple files in batch
        """
        uploaded_images = []
        failed_files = []
        processed_count = 0
        
        for file in files:
            try:
                db_image = await self.upload_file(
                    db=db,
                    file=file,
                    user_id=user_id,
                    storage_type=storage_type,
                    description=description,
                    upload_session_id=upload_session_id
                )
                
                uploaded_images.append(db_image)
                processed_count += 1
                
                # Update upload session progress
                if upload_session_id:
                    update_upload_session(db, upload_session_id, processed_count)
                    
            except Exception as e:
                app_logger.error(f"Batch upload error for {file.filename}: {e}")
                failed_files.append(file.filename or "unknown")
        
        return {
            "uploaded_images": uploaded_images,
            "uploaded_count": len(uploaded_images),
            "failed_count": len(failed_files),
            "failed_files": failed_files
        }


# Global upload service instance
upload_service = UploadService()