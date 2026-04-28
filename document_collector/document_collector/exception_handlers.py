"""Context managers and utilities for handling exceptions across the application."""

import logging
from typing import Optional, Type, Tuple
from types import TracebackType

# Import your specific libraries to catch their exceptions
import pymongo.errors

# Setup a default logger, should be used in case no custom logger is provided
_logger = logging.getLogger(__name__)


class OperationStatus:
    """
    A mutable object to track the success/failure of the block.
    This is what is yielded by the context manager.
    At the end of the block, its attributes are updated. Therefore, we can take different actions based on the outcome.
    In future self.success might be extended to include more detailed status codes.
    """

    def __init__(self):
        self.success: bool = False
        self.error: Optional[BaseException] = (
            None  # __exit__ exc_val has BaseException type
        )


class BaseSafeContext:
    """
    Base context manager that handles timing and generic logging.
    Subclasses define specific exceptions to catch.
    """

    def __init__(self, logger: logging.Logger = _logger, log_error: bool = True):
        """Initialize the context manager.:

        Args:
            logger: Logger instance to use for logging. Custom logger or global _logger
            log_error: Whether to log errors when they occur.
        Internal attributes:
            exceptions_to_catch: Tuple of exception types to catch. Override in subclasses.
            context_name: Name of the context for logging purposes. Override in subclasses.
        Mutable attributes:
            status: OperationStatus instance to track success/failure.
        """
        self.logger = logger
        self.log_error = log_error
        self.status = (
            OperationStatus()
        )  # persists after context exit so the caller can inspect it
        # Override these in subclasses
        # TODO might be a good idea to have different log messages for different exception types
        self.exceptions_to_catch: Tuple[Type[BaseException], ...] = (Exception,)
        self.context_name: str = "General Operation"

    def __enter__(self) -> OperationStatus:
        """This is what is assigned to the variable after 'as' in the with statement."""
        return self.status

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        """Handle exceptions and log as needed.

        Args:
            exc_type: The type of exception raised (if any).
            exc_val: The exception instance raised (if any).
                Type is BaseException which also catches SystemExit, KeyboardInterrupt.
            exc_tb: The traceback object (if any).
        Returns:
            True to suppress the exception, False to propagate it.
            We don't want to crash the app on expected exceptions.
        """
        if exc_type is None:
            # No exception occurred
            self.status.success = True
            return True

        # Check if the exception is one we expect
        if issubclass(exc_type, self.exceptions_to_catch):
            self.status.success = False
            self.status.error = exc_val

            if self.log_error:
                self.logger.error("%s Failed : %s", self.context_name, str(exc_val))

            # Return True to SWALLOW the exception (so the app doesn't crash)
            return True

        # If it's an unexpected exception (e.g., KeyboardInterrupt), let it crash
        return False


# --- Specific Implementations ---


class MongoSafeContext(BaseSafeContext):
    """
    Specifically handles MongoDB errors.
    """

    def __init__(self, logger: logging.Logger = _logger, log_error: bool = True):
        super().__init__(logger, log_error)
        self.exceptions_to_catch = (pymongo.errors.PyMongoError, Exception)
        self.context_name = "MongoDB Access"
