"""
Logging configuration and utilities.

Why structured logging?
- Production debugging: Trace requests through logs with correlation IDs
- Metrics: Parse logs for performance monitoring
- Alerting: Grep errors and failures automatically
- Compliance: Audit trail for sensitive operations
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict
from app.config import settings
# pyrefly: ignore [missing-import]
import structlog


def setup_logging():
    """
    Configure both standard and structured logging.
    
    This function is called at application startup in main.py.
    """
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class RequestLogger:
    """Log incoming requests with correlation ID."""
    
    @staticmethod
    def log_request(method: str, url: str, user_id: str = None, metadata: Dict[str, Any] = None):
        """Log an incoming request."""
        logger = get_logger('http')
        logger.info(
            'http_request',
            method=method,
            url=url,
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            metadata=metadata or {}
        )
    
    @staticmethod
    def log_response(method: str, url: str, status_code: int, response_time_ms: float, user_id: str = None):
        """Log an outgoing response."""
        logger = get_logger('http')
        level = 'info' if 200 <= status_code < 400 else 'warning' if 400 <= status_code < 500 else 'error'
        
        getattr(logger, level)(
            'http_response',
            method=method,
            url=url,
            status_code=status_code,
            response_time_ms=round(response_time_ms, 2),
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat()
        )


class ErrorLogger:
    """Log errors with full context."""
    
    @staticmethod
    def log_error(error_type: str, error_msg: str, context: Dict[str, Any] = None, exc_info: bool = False):
        """Log an error with context."""
        logger = get_logger('error')
        logger.error(
            'application_error',
            error_type=error_type,
            error_msg=error_msg,
            context=context or {},
            timestamp=datetime.utcnow().isoformat(),
            exc_info=exc_info
        )
    
    @staticmethod
    def log_critical(critical_msg: str, context: Dict[str, Any] = None):
        """Log a critical error that requires immediate attention."""
        logger = get_logger('critical')
        logger.critical(
            'critical_error',
            message=critical_msg,
            context=context or {},
            timestamp=datetime.utcnow().isoformat()
        )
