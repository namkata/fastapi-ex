import os
import uuid
import shutil
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.orm import Session
from PIL import Image as PILImage
import io

from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image, ProcessingTask, UploadSession
from app.schemas.image import StorageType, ProcessStatus


def validate_image_file(file: UploadFile) -> bool:
    filename = file.filename or ""
    content_type = file.content_type or ""

    ext = filename.split('.')[-1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        app_logger.warning(f"Invalid file extension: {ext}")
        return False

    if not content_type.startswith('image/'):
        app_logger.warning(f"Invalid content type: {content_type}")
        return False

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > settings.MAX_FILE_SIZE:
        app_logger.warning(f"File too large: {file_size} bytes")
        return False

    try:
        img = PILImage.open(io.BytesIO(file.file.read()))
        img.verify()
        file.file.seek(0)
        return True
    except Exception as e:
        app_logger.error(f"Invalid image file: {e}")
        file.file.seek(0)
        return False


def get_image_info(file: UploadFile) -> Dict[str, Any]:
    """
    Lấy thông tin của file ảnh
    """
    # Đọc file
    file_content = file.file.read()
    file.file.seek(0)  # Reset file position
    
    # Lấy kích thước file
    file_size = len(file_content)
    
    # Lấy thông tin ảnh
    try:
        img = PILImage.open(io.BytesIO(file_content))
        width, height = img.size
        format = img.format.lower()
    except Exception as e:
        app_logger.error(f"Error getting image info: {e}")
        width, height = None, None
        format = None
    
    return {
        "file_size": file_size,
        "width": width,
        "height": height,
        "format": format,
    }


def save_upload_file_local(file: UploadFile, destination: str) -> str:
    """
    Lưu file upload vào thư mục local
    """
    # Tạo thư mục nếu chưa tồn tại
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    
    # Lưu file
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return destination


def create_image_record(
        db: Session,
        file: UploadFile,
        user_id: int,
        storage_type: StorageType,
        description: Optional[str] = None,
        upload_session_id: Optional[int] = None,
) -> Image:
    """
    Create an Image record in the database.
    """
    # Ensure filename and content_type are not None
    original_filename = file.filename or "unknown.jpg"
    content_type = file.content_type or "application/octet-stream"

    # Generate a random filename
    ext = original_filename.split('.')[-1].lower()
    filename = f"{uuid.uuid4()}.{ext}"

    # Define the local storage path
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    # Extract image metadata
    image_info = get_image_info(file)

    # Save file locally if needed
    if storage_type == StorageType.LOCAL:
        save_upload_file_local(file, file_path)

    # Create Image record
    db_image = Image(
        filename=filename,
        original_filename=original_filename,
        file_path=file_path if storage_type == StorageType.LOCAL else None,
        file_size=image_info["file_size"],
        file_type=content_type,
        width=image_info["width"],
        height=image_info["height"],
        description=description,
        storage_type=storage_type,
        storage_path=file_path if storage_type == StorageType.LOCAL else None,
        is_processed=False,
        process_status=ProcessStatus.PENDING,
        owner_id=user_id,
    )

    # Save to database
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    app_logger.info(f"Created image record: {db_image.id}")
    return db_image

def create_upload_session(db: Session, user_id: int, total_files: int) -> UploadSession:
    """
    Tạo phiên upload mới
    """
    db_session = UploadSession(
        user_id=user_id,
        total_files=total_files,
        processed_files=0,
        status="in_progress",
    )
    
    # Lưu vào database
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    app_logger.info(f"Created upload session: {db_session.id}")
    return db_session


def update_upload_session(db: Session, session_id: int, processed_files: int) -> UploadSession:
    """
    Cập nhật trạng thái phiên upload
    """
    db_session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
    if not db_session:
        app_logger.error(f"Upload session not found: {session_id}")
        raise ValueError("Upload session not found")
    
    # Cập nhật số lượng file đã xử lý
    db_session.processed_files = processed_files
    
    # Kiểm tra nếu đã xử lý hết file
    if processed_files >= db_session.total_files:
        db_session.status = "completed"
        db_session.completed_at = datetime.utcnow()
    
    # Lưu vào database
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    app_logger.info(f"Updated upload session: {db_session.id}, processed: {processed_files}")
    return db_session


def create_processing_task(
    db: Session, 
    image_id: int, 
    task_type: str, 
    params: Dict[str, Any]
) -> ProcessingTask:
    """
    Tạo task xử lý ảnh
    """
    db_task = ProcessingTask(
        image_id=image_id,
        task_type=task_type,
        params=str(params),  # Convert to string
        status=ProcessStatus.PENDING,
    )
    
    # Lưu vào database
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    app_logger.info(f"Created processing task: {db_task.id}")
    return db_task


def get_image(db: Session, image_id: int) -> Optional[Image]:
    """
    Lấy thông tin ảnh theo ID
    """
    return db.query(Image).filter(Image.id == image_id).first()


def get_images(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    user_id: Optional[int] = None
) -> Tuple[List[Image], int]:
    """
    Lấy danh sách ảnh với phân trang
    """
    query = db.query(Image)
    
    # Lọc theo user_id nếu có
    if user_id is not None:
        query = query.filter(Image.owner_id == user_id)
    
    # Đếm tổng số bản ghi
    total = query.count()
    
    # Lấy dữ liệu với phân trang
    images = query.order_by(Image.created_at.desc()).offset(skip).limit(limit).all()
    
    return images, total


def update_image(db: Session, image_id: int, image_data: Dict[str, Any]) -> Optional[Image]:
    """
    Cập nhật thông tin ảnh
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        app_logger.warning(f"Image not found: {image_id}")
        return None
    
    # Cập nhật thông tin
    for field, value in image_data.items():
        if hasattr(db_image, field):
            setattr(db_image, field, value)
    
    # Lưu vào database
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    app_logger.info(f"Updated image: {db_image.id}")
    return db_image


def delete_image(db: Session, image_id: int) -> bool:
    """
    Xóa ảnh
    """
    db_image = get_image(db, image_id=image_id)
    if not db_image:
        app_logger.warning(f"Image not found: {image_id}")
        return False
    
    # Xóa file nếu lưu ở local
    if db_image.storage_type == StorageType.LOCAL and db_image.file_path:
        try:
            if os.path.exists(db_image.file_path):
                os.remove(db_image.file_path)
        except Exception as e:
            app_logger.error(f"Error deleting file: {e}")
    
    # Xóa bản ghi
    db.delete(db_image)
    db.commit()
    
    app_logger.info(f"Deleted image: {image_id}")
    return True