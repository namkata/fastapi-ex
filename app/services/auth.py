from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import app_logger
from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import TokenPayload

# Thiết lập OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# Thiết lập context cho password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Kiểm tra mật khẩu
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Tạo hash cho mật khẩu
    """
    return pwd_context.hash(password)


def create_access_token(subject: int, expires_delta: Optional[timedelta] = None) -> str:
    """
    Tạo JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Xác thực người dùng
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """
    Lấy thông tin người dùng hiện tại từ token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        
        if token_data.sub is None:
            app_logger.error("Token missing sub")
            raise credentials_exception

        if token_data.exp is None or datetime.fromtimestamp(token_data.exp) < datetime.utcnow():
            app_logger.error("Token expired or missing exp")
            raise credentials_exception

    except JWTError as e:
        app_logger.error(f"JWT error: {e}")
        raise credentials_exception
    
    user = db.query(User).filter(User.id == token_data.sub).first()
    if user is None:
        app_logger.error(f"User not found: {token_data.sub}")
        raise credentials_exception
    
    if not user.is_active:
        app_logger.error(f"Inactive user: {user.username}")
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Kiểm tra người dùng có active không
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Kiểm tra người dùng có quyền admin không
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user doesn't have enough privileges"
        )
    return current_user