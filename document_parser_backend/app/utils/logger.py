"""Lightweight helpers to ensure every module gets a configured logger."""

from app.config.logging_config import setup_logger, ContextFilter


def get_logger(name):
	"""Return a logger that is guaranteed to have handlers configured."""
	return setup_logger(name)


__all__ = ['setup_logger', 'get_logger', 'ContextFilter']
