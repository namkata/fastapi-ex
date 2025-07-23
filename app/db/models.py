import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    images: Mapped[List["Image"]] = relationship("Image", back_populates="owner")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(255))
    file_size: Mapped[Optional[int]] = mapped_column()
    file_type: Mapped[Optional[str]] = mapped_column(String(50))
    width: Mapped[Optional[int]] = mapped_column()
    height: Mapped[Optional[int]] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Storage information
    storage_type: Mapped[Optional[str]] = mapped_column(String(20))
    storage_path: Mapped[Optional[str]] = mapped_column(String(255))
    seaweedfs_fid: Mapped[Optional[str]] = mapped_column(String(255))
    s3_key: Mapped[Optional[str]] = mapped_column(String(255))
    s3_url: Mapped[Optional[str]] = mapped_column(String(255))

    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    process_status: Mapped[str] = mapped_column(String(20), default="pending")
    process_error: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    owner: Mapped["User"] = relationship("User", back_populates="images")
    thumbnails: Mapped[List["Thumbnail"]] = relationship(
        "Thumbnail", back_populates="image"
    )

    __mapper_args__ = {"confirm_deleted_rows": False}


class Thumbnail(Base):
    __tablename__ = "thumbnails"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"))
    size: Mapped[str] = mapped_column(String(20))
    width: Mapped[int] = mapped_column()
    height: Mapped[int] = mapped_column()
    file_path: Mapped[Optional[str]] = mapped_column(String(255))

    # Storage information
    storage_type: Mapped[str] = mapped_column(String(20))
    storage_path: Mapped[Optional[str]] = mapped_column(String(255))
    seaweedfs_fid: Mapped[Optional[str]] = mapped_column(String(255))
    s3_key: Mapped[Optional[str]] = mapped_column(String(255))
    s3_url: Mapped[Optional[str]] = mapped_column(String(255))

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    image: Mapped["Image"] = relationship("Image", back_populates="thumbnails")


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"))
    task_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    params: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    error: Mapped[str] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    total_files: Mapped[int] = mapped_column(default=0)
    processed_files: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

# Example model (you need to create this in your models.py)
class SeaweedFSFileMapping(Base):
    __tablename__ = "seaweedfs_file_mappings"
    key = mapped_column(String, primary_key=True, index=True)
    fid = mapped_column(String, nullable=False)
