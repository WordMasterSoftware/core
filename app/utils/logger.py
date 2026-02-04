import logging
import sys
from app.config import settings

def setup_logging():
    """
    Configure structured logging for the application.
    """
    # Create logger
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    # Check if handlers already exist to avoid duplicates
    if not logger.handlers:
        logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid double logging
    logger.propagate = False

    # Also configure root logger to capture uvicorn/fastapi logs if needed,
    # but usually we want to control our own namespace 'app'
    # To capture everything:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[console_handler]
    )

    return logger
