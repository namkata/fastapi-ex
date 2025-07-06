from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import get_password_hash
from app.core.logging import app_logger


def get_user(db: Session, user_id: int) -> Optional[User]:
    """
    Lấy thông tin user theo ID
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Lấy thông tin user theo email
    """
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Lấy thông tin user theo username
    """
    return db.query(User).filter(User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """
    Lấy danh sách users với phân trang
    """
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user_in: UserCreate) -> User:
    """
    Tạo user mới
    """
    # Kiểm tra email đã tồn tại chưa
    db_user = get_user_by_email(db, email=user_in.email)
    if db_user:
        app_logger.warning(f"Email already registered: {user_in.email}")
        raise ValueError("Email already registered")
    
    # Kiểm tra username đã tồn tại chưa
    db_user = get_user_by_username(db, username=user_in.username)
    if db_user:
        app_logger.warning(f"Username already taken: {user_in.username}")
        raise ValueError("Username already taken")
    
    # Tạo user mới
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        is_active=user_in.is_active,
    )
    
    # Lưu vào database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    app_logger.info(f"Created new user: {db_user.username}")
    return db_user


def update_user(db: Session, user_id: int, user_in: UserUpdate) -> Optional[User]:
    """
    Cập nhật thông tin user
    """
    db_user = get_user(db, user_id=user_id)
    if not db_user:
        app_logger.warning(f"User not found: {user_id}")
        return None
    
    # Cập nhật thông tin
    update_data = user_in.dict(exclude_unset=True)
    
    # Xử lý password nếu có
    if "password" in update_data:
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
    
    # Cập nhật các trường khác
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    # Lưu vào database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    app_logger.info(f"Updated user: {db_user.username}")
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    """
    Xóa user
    """
    db_user = get_user(db, user_id=user_id)
    if not db_user:
        app_logger.warning(f"User not found: {user_id}")
        return False
    
    # Xóa user
    db.delete(db_user)
    db.commit()
    
    app_logger.info(f"Deleted user: {db_user.username}")
    return True