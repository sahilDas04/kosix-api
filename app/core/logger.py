import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Log format constants
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log directory
LOG_DIR = Path("logs")


def setup_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_filename: Optional[str] = None
) -> None:
    """
    Setup application-wide logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to also log to a file
        log_filename: Custom log filename (defaults to app_YYYY-MM-DD.log)
    """
    # Create logs directory if it doesn't exist
    if log_to_file:
        LOG_DIR.mkdir(exist_ok=True)
    
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_to_file:
        if log_filename is None:
            log_filename = f"app_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        file_handler = logging.FileHandler(
            LOG_DIR / log_filename,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Create a default application logger
logger = get_logger("app")
