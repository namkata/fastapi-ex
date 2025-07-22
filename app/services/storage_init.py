"""Storage backends initialization"""

from app.core.logging import app_logger
from app.services.storage_manager import storage_manager
from app.services.s3 import S3Service
from app.services.seaweedfs import SeaweedFSService
from app.services.local_storage import LocalStorageService


def initialize_storage_backends() -> None:
    """
    Initialize and register all storage backends with the storage manager
    """
    app_logger.info("Initializing storage backends...")
    
    # Initialize Local Storage
    try:
        local_storage = LocalStorageService()
        storage_manager.register_backend("local", local_storage, is_default=True)
        app_logger.info(f"Local storage registered (available: {local_storage.is_available()})")
    except Exception as e:
        app_logger.error(f"Failed to initialize local storage: {e}")
    
    # Initialize S3 Storage
    try:
        s3_storage = S3Service()
        storage_manager.register_backend("s3", s3_storage)
        app_logger.info(f"S3 storage registered (available: {s3_storage.is_available()})")
    except Exception as e:
        app_logger.error(f"Failed to initialize S3 storage: {e}")
    
    # Initialize SeaweedFS Storage
    try:
        seaweedfs_storage = SeaweedFSService()
        storage_manager.register_backend("seaweedfs", seaweedfs_storage)
        app_logger.info(f"SeaweedFS storage registered (available: {seaweedfs_storage.is_available()})")
    except Exception as e:
        app_logger.error(f"Failed to initialize SeaweedFS storage: {e}")
    
    # Log final status
    backends_status = storage_manager.get_available_backends()
    available_backends = [name for name, available in backends_status.items() if available]
    unavailable_backends = [name for name, available in backends_status.items() if not available]
    
    app_logger.info(f"Storage initialization complete:")
    app_logger.info(f"  Available backends: {available_backends}")
    if unavailable_backends:
        app_logger.warning(f"  Unavailable backends: {unavailable_backends}")
    
    if not available_backends:
        app_logger.error("No storage backends are available! File uploads will fail.")


def get_storage_health_report() -> dict:
    """
    Get comprehensive health report for all storage backends
    """
    return {
        "backends": storage_manager.health_check(),
        "available_count": len([b for b in storage_manager.get_available_backends().values() if b]),
        "total_count": len(storage_manager.get_available_backends())
    }