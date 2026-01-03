"""
Comprehensive logging configuration for NPS IVR.

Supports both VM and containerized environments:
- VM: Logs to files with rotation + systemd journal
- Container: Logs to STDOUT/STDERR for container runtime collection
- Structured JSON logging for easy parsing by log aggregators

Environment Variables:
- LOG_LEVEL: debug, info, warning, error (default: info)
- LOG_FORMAT: json or text (default: json for container, text for VM)
- LOG_TO_FILE: true/false (default: true for VM, false for container)
- LOG_DIR: Directory for log files (default: /var/log/nps-ivr)
"""

import logging
import logging.handlers
import sys
import os
import json
from datetime import datetime
from typing import Any, Dict
from pathlib import Path
from queue import Queue
import atexit


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Makes logs easily parseable by Azure Monitor, ELK, Datadog, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        try:
            log_data: Dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # Add extra fields if present (for contextual logging)
            if hasattr(record, "session_id"):
                log_data["session_id"] = record.session_id
            if hasattr(record, "channel"):
                log_data["channel"] = record.channel
            if hasattr(record, "call_sid"):
                log_data["call_sid"] = record.call_sid
            if hasattr(record, "phone"):
                log_data["phone"] = record.phone
            if hasattr(record, "duration_ms"):
                log_data["duration_ms"] = record.duration_ms

            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_data)
        except Exception as e:
            # If formatting fails, return a basic fallback message
            # This ensures logging never crashes the application
            fallback = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "message": f"Logging error: {str(e)} | Original message: {getattr(record, 'msg', 'unknown')}",
                "formatter_error": True
            }
            return json.dumps(fallback)


class ReadableFormatter(logging.Formatter):
    """
    Human-readable formatter for local development and VM logs.
    """

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def is_container_environment() -> bool:
    """Detect if running in a container"""
    return (
        os.path.exists("/.dockerenv") or
        os.environ.get("KUBERNETES_SERVICE_HOST") is not None or
        os.environ.get("CONTAINER") == "true"
    )


def setup_logging():
    """
    Configure comprehensive logging for the application.
    Uses QueueHandler for non-blocking async-safe logging.
    """
    # CRITICAL: Disable raising exceptions from logging to prevent crashes
    # Logging should NEVER crash the application
    logging.raiseExceptions = False

    # Configuration from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json" if is_container_environment() else "text")
    log_to_file = os.getenv("LOG_TO_FILE", "false" if is_container_environment() else "true").lower() == "true"
    log_dir = Path(os.getenv("LOG_DIR", "/var/log/nps-ivr"))
    use_async_logging = os.getenv("ASYNC_LOGGING", "true").lower() == "true"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Choose formatter
    if log_format == "json":
        formatter = StructuredFormatter()
    else:
        formatter = ReadableFormatter()

    # Create a queue for async logging (non-blocking)
    if use_async_logging:
        log_queue = Queue(-1)  # Unlimited queue size
        queue_handler = logging.handlers.QueueHandler(log_queue)
        root_logger.addHandler(queue_handler)

        # Create listener that processes logs in background thread
        # This handler does the actual (blocking) I/O
        listener_handlers = []

        # Console handler (STDOUT for containers, systemd journal for VMs)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        listener_handlers.append(console_handler)
    else:
        # Synchronous logging (old behavior)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        listener_handlers = None

    # File handlers (only for VMs, not containers)
    if log_to_file:
        try:
            # Create log directory if it doesn't exist
            log_dir.mkdir(parents=True, exist_ok=True)

            # Main application log with rotation
            app_log_file = log_dir / "nps-ivr.log"
            file_handler = logging.handlers.RotatingFileHandler(
                app_log_file,
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=10,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            if use_async_logging:
                listener_handlers.append(file_handler)
            else:
                root_logger.addHandler(file_handler)

            # Separate error log
            error_log_file = log_dir / "nps-ivr-error.log"
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            if use_async_logging:
                listener_handlers.append(error_handler)
            else:
                root_logger.addHandler(error_handler)

            # Voice/SMS transaction log (business events)
            transaction_log_file = log_dir / "transactions.log"
            transaction_handler = logging.handlers.RotatingFileHandler(
                transaction_log_file,
                maxBytes=100 * 1024 * 1024,  # 100MB
                backupCount=20,
                encoding="utf-8"
            )
            transaction_handler.setFormatter(StructuredFormatter())  # Always JSON for transactions
            transaction_handler.addFilter(lambda record: record.name == "app.transactions")
            if use_async_logging:
                listener_handlers.append(transaction_handler)
            else:
                root_logger.addHandler(transaction_handler)

            logging.info(f"File logging enabled: {log_dir}")

        except PermissionError:
            logging.warning(f"No permission to write logs to {log_dir}, using console only")

    # Start the queue listener in a background thread (for async logging)
    if use_async_logging and listener_handlers:
        listener = logging.handlers.QueueListener(
            log_queue,
            *listener_handlers,
            respect_handler_level=True
        )
        listener.start()

        # Ensure listener stops on shutdown
        atexit.register(listener.stop)

    # Log startup info
    env_type = "container" if is_container_environment() else "VM"
    async_status = "async" if use_async_logging else "sync"
    logging.info(f"Logging initialized - Environment: {env_type}, Level: {log_level}, Format: {log_format}, File: {log_to_file}, Mode: {async_status}")


# Transaction logger for business events
def get_transaction_logger():
    """
    Get a dedicated logger for business transactions (voice calls, SMS, lead submissions).
    This creates structured logs that are easy to query and analyze.
    """
    return logging.getLogger("app.transactions")


# Contextual logging helpers
class LogContext:
    """
    Context manager for adding extra fields to log records.

    Usage:
        with LogContext(session_id=123, channel="voice"):
            logger.info("Processing call")  # Will include session_id and channel
    """

    def __init__(self, **kwargs):
        self.context = kwargs
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)
