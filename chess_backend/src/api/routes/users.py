from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db import get_db
from src.models import User
from src.schemas import CreateUserRequest, ErrorResponse, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
    summary="Create a user",
    description="Create a new user with a unique username.",
    operation_id="create_user",
)
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db)) -> UserResponse:
    """Create a new user."""
    user = User(username=payload.username.strip())
    if not user.username:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already exists.")
    db.refresh(user)

    return UserResponse(id=user.id, username=user.username, created_at=user.created_at)


# PUBLIC_INTERFACE
@router.get(
    "/{user_id}",
    response_model=UserResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a user by ID",
    description="Fetch a user record by user_id.",
    operation_id="get_user",
)
def get_user(user_id: str, db: Session = Depends(get_db)) -> UserResponse:
    """Fetch a user by ID."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserResponse(id=user.id, username=user.username, created_at=user.created_at)
