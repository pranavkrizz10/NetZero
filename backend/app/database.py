"""Database engine and session setup.

Uses SQLite for zero-config portability. The whole app runs from a single
file (netzero.db) that is created on first launch. Swap the URL for
PostgreSQL in one line if you outgrow SQLite.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# DB file lives at the backend root, next to this package.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "netzero.db")
DATABASE_URL = os.environ.get("NETZERO_DATABASE_URL", f"sqlite:///{DB_PATH}")

# check_same_thread=False is required for SQLite under a threaded server.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
