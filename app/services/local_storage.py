import os
import shutil
import uuid
from typing import BinaryIO, Optional
from urllib.parse import quote
from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import app_logger
from app.services.storage_manager import StorageBackend


class LocalStorageService(StorageBackend):
    """Local file system storage backend"""
    
    def _initialize(self) -> None:
        """Initialize local storage"""
        try:
            self.upload_dir = settings.UPLOAD_DIR
            
            # Create upload directory if it doesn't exist
            os.makedirs(self.upload_dir, exist_ok=True)
            
            # Test write permissions
            test_file = os.path.join(self.upload_dir, f"test_{uuid.uuid4().hex}.tmp")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                self.available = True
                app_logger.info(f"Local storage initialized successfully (dir: {self.upload_dir})")
            except Exception as test_e:
                app_logger.error(f"Local storage write test failed: {test_e}")
                self.available = False
                
        except Exception as e:
            app_logger.error(f"Error initializing local storage: {e}")
            self.available = False
    
    def upload_file(self, file: BinaryIO, key: str, **kwargs) -> bool:
        """Upload file to local storage"""
        if not self.available:
            app_logger.warning("Local storage is not available")
            return False
        
        try:
            # Create full file path
            file_path = os.path.join(self.upload_dir, key)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write file
            file.seek(0)
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(file, f)
            
            app_logger.info(f"Uploaded file to local storage: {key}")
            return True
            
        except Exception as e:
            app_logger.error(f"Error uploading file to local storage: {e}")
            return False
    
    def upload_from_upload_file(self, upload_file: UploadFile, key: Optional[str] = None, **kwargs) -> bool:
        """Upload FastAPI UploadFile to local storage"""
        if not self.available:
            app_logger.warning("Local storage is not available")
            return False
        
        try:
            filename = upload_file.filename or "unnamed_file"
            if key is None:
                ext = os.path.splitext(filename)[-1].lower()
                key = f"uploads/{uuid.uuid4().hex}{ext}"
            
            upload_file.file.seek(0)
            return self.upload_file(upload_file.file, key, **kwargs)
            
        except Exception as e:
            app_logger.error(f"Error uploading UploadFile to local storage: {e}")
            return False
    
    def upload_from_path(self, file_path: str, key: Optional[str] = None, **kwargs) -> bool:
        """Upload file from local path to local storage (copy)"""
        if not self.available:
            app_logger.warning("Local storage is not available")
            return False
        
        try:
            if not os.path.exists(file_path):
                app_logger.error(f"Source file not found: {file_path}")
                return False
            
            if key is None:
                filename = os.path.basename(file_path)
                ext = os.path.splitext(filename)[-1].lower()
                key = f"uploads/{uuid.uuid4().hex}{ext}"
            
            # Create destination path
            dest_path = os.path.join(self.upload_dir, key)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Copy file
            shutil.copy2(file_path, dest_path)
            
            app_logger.info(f"Copied file to local storage: {key}")
            return True
            
        except Exception as e:
            app_logger.error(f"Error copying file to local storage: {e}")
            return False
    
    def get_file_url(self, key: str) -> Optional[str]:
        """Get file URL for local storage (relative path)"""
        if not self.available:
            app_logger.warning("Local storage is not available")
            return None
        
        try:
            # For local storage, return a relative URL that can be served by the web server
            # This assumes the upload directory is served as static files
            encoded_key = quote(key)
            return f"/static/uploads/{encoded_key}"
            
        except Exception as e:
            app_logger.error(f"Error generating file URL: {e}")
            return None
    
    def delete_file(self, key: str) -> bool:
        """Delete file from local storage"""
        if not self.available:
            app_logger.warning("Local storage is not available")
            return False
        
        try:
            file_path = os.path.join(self.upload_dir, key)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                app_logger.info(f"Deleted file from local storage: {key}")
                
                # Try to remove empty directories
                try:
                    dir_path = os.path.dirname(file_path)
                    if dir_path != self.upload_dir:
                        os.rmdir(dir_path)
                except OSError:
                    pass  # Directory not empty, which is fine
                
                return True
            else:
                app_logger.warning(f"File not found for deletion: {key}")
                return False
                
        except Exception as e:
            app_logger.error(f"Error deleting file from local storage: {e}")
            return False
    
    def download_file(self, key: str) -> Optional[bytes]:
        """Download file content from local storage"""
        if not self.available:
            app_logger.warning("Local storage is not available")
            return None
        
        try:
            file_path = os.path.join(self.upload_dir, key)
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    return f.read()
            else:
                app_logger.warning(f"File not found: {key}")
                return None
                
        except Exception as e:
            app_logger.error(f"Error downloading file from local storage: {e}")
            return None
    
    def file_exists(self, key: str) -> bool:
        """Check if file exists in local storage"""
        if not self.available:
            return False
        
        try:
            file_path = os.path.join(self.upload_dir, key)
            return os.path.exists(file_path)
            
        except Exception as e:
            app_logger.error(f"Error checking file existence: {e}")
            return False
    
    def get_file_path(self, key: str) -> Optional[str]:
        """Get absolute file path for local storage"""
        if not self.available:
            return None
        
        try:
            file_path = os.path.join(self.upload_dir, key)
            return file_path if os.path.exists(file_path) else None
            
        except Exception as e:
            app_logger.error(f"Error getting file path: {e}")
            return None


# Global local storage service instance
local_storage_service = LocalStorageService()