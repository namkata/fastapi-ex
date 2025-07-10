from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.logging import app_logger
from app.db.session import get_db
from app.db.models import User
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate
from app.services.auth import get_current_active_user, get_current_admin_user
from app.services.user import get_user, get_users, create_user, update_user, delete_user

# Create router
router = APIRouter()


@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_in: UserCreate, db: Session = Depends(get_db)
) -> UserSchema:
    """
    Create a new user.
    """
    try:
        db_user = create_user(db, user_in)
        return db_user
    except ValueError as e:
        app_logger.warning(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=UserSchema)
async def read_users_me(
    current_user: User = Depends(get_current_active_user),
) -> UserSchema:
    """
    Get the currently authenticated user's profile.
    """
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_user_me(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserSchema:
    """
    Update the currently authenticated user's information.
    """
    db_user = update_user(db, current_user.id, user_in)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return db_user


@router.get("/", response_model=List[UserSchema])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> List[UserSchema]:
    """
    Get a list of all users (admin only).
    """
    users = get_users(db, skip=skip, limit=limit)
    return [UserSchema.from_orm(user) for user in users]


@router.get("/{user_id}", response_model=UserSchema)
async def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserSchema:
    """
    Get a user by ID. Admins can access any user; regular users can only access themselves.
    """
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    db_user = get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return db_user


@router.put("/{user_id}", response_model=UserSchema)
async def update_user_by_id(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> UserSchema:
    """
    Update a user by ID (admin only).
    """
    db_user = update_user(db, user_id, user_in)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return db_user


@router.delete("/{user_id}", response_model=UserSchema)
async def delete_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> UserSchema:
    """
    Delete a user by ID (admin only). Users cannot delete themselves.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    db_user = get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    success = delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user",
        )

    return db_user
