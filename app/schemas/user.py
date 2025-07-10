from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserInDBBase(UserBase):
    id: int
    is_admin: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class User(UserInDBBase):
    """User schema for response"""
    pass


class UserInDB(UserInDBBase):
    """User schema with password hash for DB operations"""
    hashed_password: str