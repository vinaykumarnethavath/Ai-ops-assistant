"""
Structured logging utilities for AI Operations Assistant.
Provides JSON-formatted logs with correlation IDs for request tracing.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Optional
from functools import lru_cache
import uuid


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
        if hasattr(record, "agent"):
            log_obj["agent"] = record.agent
        if hasattr(record, "tool"):
            log_obj["tool"] = record.tool
        if hasattr(record, "step"):
            log_obj["step"] = record.step
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms
            
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that adds context to all log messages."""
    
    def __init__(self, logger: logging.Logger, correlation_id: Optional[str] = None):
        super().__init__(logger, {})
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
    
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["correlation_id"] = self.correlation_id
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """Configure application logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]


@lru_cache(maxsize=100)
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def get_context_logger(name: str, correlation_id: Optional[str] = None) -> ContextAdapter:
    """Get a logger with correlation ID context."""
    logger = get_logger(name)
    return ContextAdapter(logger, correlation_id)
