from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Create database engine
logger.info(f"Creating database engine for host: {settings.DB_HOST}:{settings.DB_PORT}")
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
logger.debug("Database engine created successfully")

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    Yields a session and ensures it's closed after use.
    """
    db = SessionLocal()
    logger.debug("Database session created")
    try:
        yield db
    finally:
        db.close()
        logger.debug("Database session closed")
