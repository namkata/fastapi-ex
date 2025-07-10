from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import app_logger

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {},
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Dependency to get DB session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Function to create database tables
def create_tables() -> None:
    try:
        app_logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        app_logger.info("Database tables created successfully")
    except Exception as e:
        app_logger.error(f"Error creating database tables: {e}")
        raise
