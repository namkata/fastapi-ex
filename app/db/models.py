from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    images = relationship("Image", back_populates="owner")


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(255))  # Local file path
    file_size = Column(Integer)  # Size in bytes
    file_type = Column(String(50))  # MIME type
    width = Column(Integer)  # Image width
    height = Column(Integer)  # Image height
    description = Column(Text)  # Image description
    
    # Storage information
    storage_type = Column(String(20))  # 'local', 'seaweedfs', or 's3'
    storage_path = Column(String(255))  # Path or URL in storage system
    seaweedfs_fid = Column(String(255))  # SeaweedFS file ID
    s3_key = Column(String(255))  # S3 object key
    s3_url = Column(String(255))  # S3 URL
    
    # Processing status
    is_processed = Column(Boolean, default=False)  # Whether image has been processed
    process_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    process_error = Column(Text)  # Error message if processing failed
    
    # Metadata
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    owner = relationship("User", back_populates="images")
    thumbnails = relationship("Thumbnail", back_populates="image")


class Thumbnail(Base):
    __tablename__ = "thumbnails"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"))
    size = Column(String(20))  # e.g., 'small', 'medium', 'large'
    width = Column(Integer)
    height = Column(Integer)
    file_path = Column(String(255))  # Local file path
    
    # Storage information
    storage_type = Column(String(20))  # 'local', 'seaweedfs', or 's3'
    storage_path = Column(String(255))  # Path or URL in storage system
    seaweedfs_fid = Column(String(255))  # SeaweedFS file ID
    s3_key = Column(String(255))  # S3 object key
    s3_url = Column(String(255))  # S3 URL
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    image = relationship("Image", back_populates="thumbnails")


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(Integer, ForeignKey("images.id"))
    task_type = Column(String(50))  # e.g., 'resize', 'crop', 'filter'
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    params = Column(Text)  # JSON string with task parameters
    result = Column(Text)  # JSON string with task results
    error = Column(Text)  # Error message if task failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(50), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"))
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    status = Column(String(20), default="in_progress")  # in_progress, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))