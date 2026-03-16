"""
Database configuration and session management.

This module sets up SQLAlchemy engine, session, and base class for ORM models.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Generator

# Database URL from environment or default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/test_reports.db")

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific settings
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Allow multi-threading
        echo=False,  # Set to True for SQL debugging
    )

    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    # PostgreSQL or other database
    engine = create_engine(DATABASE_URL, echo=False)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db() -> Generator:
    """
    Dependency function to get database session.

    Yields:
        Database session that automatically closes after use.

    Example:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.

    This should be called once when setting up the application.
    """
    # Ensure data directory exists
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Import models to register them with Base
    from storage import models  # noqa: F401

    # Debug: Check what tables are registered
    print(f"Registered tables: {list(Base.metadata.tables.keys())}")

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DATABASE_URL}")


def drop_db():
    """
    Drop all tables from the database.

    WARNING: This will delete all data! Use only for testing or reset.
    """
    from storage import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    print("All tables dropped from database")
