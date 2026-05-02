#!/usr/bin/env python3
"""
Centralized Logger Module

Provides professional, centralized logging configuration for the entire application.
Uses Python's standard logging with consistent formatting.

Usage:
    from hipaa_deidentifier.utils.logger import get_logger, set_log_level

    # Get a logger for your module
    logger = get_logger("my_module")
    logger.info("Processing started")
    logger.debug("Detailed information")

    # Set log level
    set_log_level("DEBUG")  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
"""

import logging

# Module-level logger cache
_loggers = {}


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the specified name.

    Args:
        name: Name for the logger (e.g., "presidio", "hf", "redactor")

    Returns:
        Configured logger instance
    """
    global _loggers

    # Return cached logger if it exists
    if name in _loggers:
        return _loggers[name]

    # Create new logger
    logger = logging.getLogger(f"hipaa_deidentifier.{name}")

    # Only configure if no handlers exist (avoid duplicate handlers)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Create console handler with formatting
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)

        # Professional format: timestamp - level - module - message
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Cache the logger
    _loggers[name] = logger
    return logger


def set_log_level(level: str) -> None:
    """
    Set the logging level for all loggers in the application.

    Args:
        level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    # Convert string level to numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Update all cached loggers
    for logger in _loggers.values():
        logger.setLevel(numeric_level)
        for handler in logger.handlers:
            handler.setLevel(numeric_level)
