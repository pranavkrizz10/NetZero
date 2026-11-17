from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from .. import models, schemas, auth as auth_utils

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.AuthOut)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = models.User(
        name=body.name.strip(),
        email=email,
        password_hash=auth_utils.hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = auth_utils.create_token(db, user.id)
    return {"token": token, "user": user}


@router.post("/login", response_model=schemas.AuthOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email.lower()).first()
    if not user or not auth_utils.verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = auth_utils.create_token(db, user.id)
    return {"token": token, "user": user}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)):
    return user
