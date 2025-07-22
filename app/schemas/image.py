from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, validator


class StorageType(str, Enum):
    LOCAL = "local"
    SEAWEEDFS = "seaweedfs"
    S3 = "s3"


class ProcessStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageBase(BaseModel):
    description: Optional[str] = None


class ImageCreate(ImageBase):
    pass


class ImageUpdate(BaseModel):
    description: Optional[str] = None


class ThumbnailBase(BaseModel):
    size: str
    width: int
    height: int


class ThumbnailCreate(ThumbnailBase):
    image_id: int


class Thumbnail(ThumbnailBase):
    id: int
    image_id: int
    file_path: Optional[str] = None
    storage_type: StorageType
    storage_path: Optional[str] = None
    seaweedfs_fid: Optional[str] = None
    s3_key: Optional[str] = None
    s3_url: Optional[str] = None
    created_at: datetime

    url: Optional[str] = None

    @validator('url', always=True)
    def calculate_url(cls, v, values):
        storage_type = values.get('storage_type')
        if storage_type == StorageType.S3:
            return values.get('s3_url')
        elif storage_type == StorageType.SEAWEEDFS:
            fid = values.get('seaweedfs_fid')
            if fid:
                from app.services.seaweedfs import seaweedfs_service
                return seaweedfs_service.get_file_url_from_fid(fid)
        elif storage_type == StorageType.LOCAL:
            file_path = values.get('file_path')
            if file_path:
                return f"http://localhost:8000/{file_path}"
            return None
        return v

    class Config:
        orm_mode = True


class Image(ImageBase):
    id: int
    filename: str
    original_filename: str
    file_path: Optional[str] = None
    file_size: int
    file_type: str
    width: Optional[int] = None
    height: Optional[int] = None

    storage_type: StorageType
    storage_path: Optional[str] = None
    seaweedfs_fid: Optional[str] = None
    s3_key: Optional[str] = None
    s3_url: Optional[str] = None

    is_processed: bool
    process_status: ProcessStatus
    process_error: Optional[str] = None

    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    thumbnails: List[Thumbnail] = []

    url: Optional[str] = None

    @validator('url', always=True)
    def calculate_url(cls, v, values):
        storage_type = values.get('storage_type')
        if storage_type == StorageType.S3:
            return values.get('s3_url')
        elif storage_type == StorageType.SEAWEEDFS:
            fid = values.get('seaweedfs_fid')
            if fid:
                from app.services.seaweedfs import seaweedfs_service
                return seaweedfs_service.get_file_url_from_fid(fid)
        elif storage_type == StorageType.LOCAL:
            file_path = values.get('file_path')
            if file_path:
                return f"http://localhost:8000/{file_path}"
            return None
        return v

    class Config:
        orm_mode = True


class ImageList(BaseModel):
    images: List[Image]
    total: int
    page: int
    size: int
    pages: int


class ProcessingTaskBase(BaseModel):
    image_id: int
    task_type: str
    params: Dict[str, Any]


class ProcessingTaskCreate(ProcessingTaskBase):
    pass


class ProcessingTask(ProcessingTaskBase):
    id: int
    task_id: str
    status: ProcessStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class UploadSessionBase(BaseModel):
    user_id: int


class UploadSessionCreate(UploadSessionBase):
    pass


class UploadSession(UploadSessionBase):
    id: int
    session_id: str
    total_files: int
    processed_files: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ImageUploadResponse(BaseModel):
    image: Image
    upload_session: Optional[UploadSession] = None
    processing_task: Optional[ProcessingTask] = None


class BatchUploadResponse(BaseModel):
    upload_session: UploadSession
    uploaded_count: int
    failed_count: int
    images: List[Image] = []
    failed_files: List[str] = []
