"""ORM models.

Money is stored in integer paise (1 rupee = 100 paise) everywhere it is
*computed on* (expense amounts, splits, settlements). Storing money as
integers avoids floating-point drift, which matters a lot for a settlement
engine that must balance to exactly zero. The API converts to/from rupees
at the edges.
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("Membership", back_populates="user")


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("Membership", back_populates="group")
    expenses = relationship("Expense", back_populates="group")
    settlements = relationship("Settlement", back_populates="group")


class Membership(Base):
    """Join table: which users belong to which group."""
    __tablename__ = "memberships"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    description = Column(String(255), nullable=False)
    amount_paise = Column(Integer, nullable=False)          # total, in paise
    category = Column(String(60), nullable=False, default="Other")
    # Was the category set by the ML model or confirmed/overridden by a human?
    category_source = Column(String(20), default="model")   # "model" | "user"
    paid_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    split_type = Column(String(20), default="equal")        # equal | exact | percent
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="expenses")
    shares = relationship("ExpenseShare", back_populates="expense",
                          cascade="all, delete-orphan")


class ExpenseShare(Base):
    """How much of an expense each participant owes, in paise."""
    __tablename__ = "expense_shares"
    id = Column(Integer, primary_key=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_paise = Column(Integer, nullable=False)

    expense = relationship("Expense", back_populates="shares")


class Settlement(Base):
    """A recorded real-world payment from one member to another."""
    __tablename__ = "settlements"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    from_user = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount_paise = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="settlements")


class Token(Base):
    """Opaque bearer tokens for simple session auth."""
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CategoryCorrection(Base):
    """Training signal: every time a user overrides the model's category
    guess, we log (description -> corrected category). The retrain job folds
    these back into the training set. This is the 'learns from feedback' loop.
    """
    __tablename__ = "category_corrections"
    id = Column(Integer, primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(60), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_in_training = Column(Boolean, default=False)
