from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, Dict, Any
from fastapi import UploadFile
from app.core.logging import app_logger


class StorageBackend(ABC):
    """Abstract base class for storage backends"""
    
    def __init__(self):
        self.available = False
        self._initialize()
    
    @abstractmethod
    def _initialize(self) -> None:
        """Initialize the storage backend"""
        pass
    
    @abstractmethod
    def upload_file(self, file: BinaryIO, key: str, **kwargs) -> bool:
        """Upload a file from a binary stream"""
        pass
    
    @abstractmethod
    def upload_from_upload_file(self, upload_file: UploadFile, key: Optional[str] = None, **kwargs) -> bool:
        """Upload a file from FastAPI UploadFile"""
        pass
    
    @abstractmethod
    def upload_from_path(self, file_path: str, key: Optional[str] = None, **kwargs) -> bool:
        """Upload a file from local path"""
        pass
    
    @abstractmethod
    def get_file_url(self, key: str) -> Optional[str]:
        """Get the public URL for a file"""
        pass
    
    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """Delete a file"""
        pass
    
    @abstractmethod
    def download_file(self, key: str) -> Optional[bytes]:
        """Download file content as bytes"""
        pass
    
    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """Check if file exists"""
        pass
    
    def is_available(self) -> bool:
        """Check if storage backend is available"""
        return self.available


class StorageManager:
    """Unified storage manager that handles multiple storage backends"""
    
    def __init__(self):
        self._backends: Dict[str, StorageBackend] = {}
        self._default_backend: Optional[str] = None
    
    def register_backend(self, name: str, backend: StorageBackend, is_default: bool = False) -> None:
        """Register a storage backend"""
        self._backends[name] = backend
        if is_default or self._default_backend is None:
            self._default_backend = name
        app_logger.info(f"Registered storage backend: {name} (available: {backend.is_available()})")
    
    def get_backend(self, name: Optional[str] = None) -> Optional[StorageBackend]:
        """Get a storage backend by name, or default if name is None"""
        backend_name = name or self._default_backend
        if not backend_name:
            app_logger.error("No storage backend specified and no default backend set")
            return None
        
        backend = self._backends.get(backend_name)
        if not backend:
            app_logger.error(f"Storage backend not found: {backend_name}")
            return None
        
        if not backend.is_available():
            app_logger.warning(f"Storage backend not available: {backend_name}")
            return None
        
        return backend
    
    def upload_file(self, file: BinaryIO, key: str, backend_name: Optional[str] = None, **kwargs) -> bool:
        """Upload file using specified or default backend"""
        backend = self.get_backend(backend_name)
        if not backend:
            return False
        return backend.upload_file(file, key, **kwargs)
    
    def upload_from_upload_file(self, upload_file: UploadFile, key: Optional[str] = None, 
                               backend_name: Optional[str] = None, **kwargs) -> bool:
        """Upload FastAPI UploadFile using specified or default backend"""
        backend = self.get_backend(backend_name)
        if not backend:
            return False
        return backend.upload_from_upload_file(upload_file, key, **kwargs)
    
    def upload_from_path(self, file_path: str, key: Optional[str] = None, 
                        backend_name: Optional[str] = None, **kwargs) -> bool:
        """Upload file from path using specified or default backend"""
        backend = self.get_backend(backend_name)
        if not backend:
            return False
        return backend.upload_from_path(file_path, key, **kwargs)
    
    def get_file_url(self, key: str, backend_name: Optional[str] = None) -> Optional[str]:
        """Get file URL using specified or default backend"""
        backend = self.get_backend(backend_name)
        if not backend:
            return None
        return backend.get_file_url(key)
    
    def delete_file(self, key: str, backend_name: Optional[str] = None) -> bool:
        """Delete file using specified or default backend"""
        backend = self.get_backend(backend_name)
        if not backend:
            return False
        return backend.delete_file(key)
    
    def download_file(self, key: str, backend_name: Optional[str] = None) -> Optional[bytes]:
        """Download file using specified or default backend"""
        backend = self.get_backend(backend_name)
        if not backend:
            return None
        return backend.download_file(key)
    
    def file_exists(self, key: str, backend_name: Optional[str] = None) -> bool:
        """Check if file exists using specified or default backend"""
        backend = self.get_backend(backend_name)
        if not backend:
            return False
        return backend.file_exists(key)
    
    def get_available_backends(self) -> Dict[str, bool]:
        """Get list of all backends and their availability status"""
        return {name: backend.is_available() for name, backend in self._backends.items()}
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all backends"""
        results = {}
        for name, backend in self._backends.items():
            results[name] = {
                'available': backend.is_available(),
                'is_default': name == self._default_backend
            }
        return results


# Global storage manager instance
storage_manager = StorageManager()