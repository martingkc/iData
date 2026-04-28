import logging
import logging.handlers
import os
from datetime import datetime

"""
change this as much as you want
"""

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Log file paths
LOG_FILE = os.path.join(LOGS_DIR, 'app.log')
ERROR_LOG_FILE = os.path.join(LOGS_DIR, 'error.log')
DEBUG_LOG_FILE = os.path.join(LOGS_DIR, 'debug.log')

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logger(name, level=logging.DEBUG):
    """
    Set up and configure a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: DEBUG)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding duplicate handlers
    if logger.hasHandlers():
        return logger
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Console Handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler (DEBUG and above) - General logs
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Error File Handler (ERROR and above)
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # Debug File Handler (DEBUG only) - For detailed debugging
    debug_handler = logging.handlers.RotatingFileHandler(
        DEBUG_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    logger.addHandler(debug_handler)
    
    return logger


def get_logger(name):
    """
    Get or create a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class ContextFilter(logging.Filter):
    """
    Add contextual information to log records.
    Useful for tracking request IDs or user information.
    """
    def filter(self, record):
        record.user_id = getattr(record, 'user_id', 'N/A')
        record.request_id = getattr(record, 'request_id', 'N/A')
        return True
