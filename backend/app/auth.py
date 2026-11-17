"""Authentication helpers.

Passwords are hashed with PBKDF2-SHA256 (pure-Python, no native wheels to
compile). Sessions use opaque random bearer tokens stored in the DB — simple,
revocable, and good enough for a course project. Swap in JWT if you want
stateless tokens.
"""
import secrets

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def create_token(db: Session, user_id: int) -> str:
    token = secrets.token_hex(24)
    db.add(models.Token(token=token, user_id=user_id))
    db.commit()
    return token


def user_for_token(db: Session, token: str):
    row = db.query(models.Token).filter(models.Token.token == token).first()
    if not row:
        return None
    return db.query(models.User).filter(models.User.id == row.user_id).first()
