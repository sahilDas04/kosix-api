from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine
from app.core.logger import get_logger

logger = get_logger(__name__)


def init_db() -> None:
    """
    Initialize database tables.
    This creates all tables defined in the models.
    For production, use Alembic migrations instead.
    """
    logger.info("Initializing database tables...")
    # Import all models here to ensure they are registered with Base
    from app.models import Account, Team, Session as SessionModel  # noqa: F401
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_db() -> None:
    """
    Drop all database tables.
    Use with caution - this will delete all data!
    """
    logger.warning("Dropping all database tables - this will delete all data!")
    Base.metadata.drop_all(bind=engine)
    logger.info("All database tables dropped")
