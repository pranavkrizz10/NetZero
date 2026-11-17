"""Shared FastAPI dependencies."""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from . import auth, models


def current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> models.User:
    """Resolve the bearer token in the Authorization header to a User."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    user = auth.user_for_token(db, token)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def require_membership(db: Session, group_id: int, user_id: int) -> None:
    """403 unless the user belongs to the group."""
    m = (
        db.query(models.Membership)
        .filter(
            models.Membership.group_id == group_id,
            models.Membership.user_id == user_id,
        )
        .first()
    )
    if not m:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of this group")
