import logging
import json
import uuid
from datetime import datetime
from typing import Any, Optional
from contextvars import ContextVar

# Context variable for trace_id
trace_id_context: ContextVar[str] = ContextVar('trace_id', default='')

class StructuredFormatter(logging.Formatter):
    """Structured JSON logging formatter with trace_id support."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'trace_id': trace_id_context.get(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add custom fields from extra parameter
        if hasattr(record, 'custom_fields'):
            log_data.update(record.custom_fields)
        
        return json.dumps(log_data)

def setup_logging(name: str) -> logging.Logger:
    """Setup structured logging for a module."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
    
    return logger

def generate_trace_id() -> str:
    """Generate a unique trace_id."""
    return str(uuid.uuid4())

def set_trace_id(trace_id: str) -> None:
    """Set the trace_id for the current context."""
    trace_id_context.set(trace_id)

def get_trace_id() -> str:
    """Get the current trace_id."""
    return trace_id_context.get()

def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs) -> None:
    """Log with custom fields and trace_id."""
    custom_fields = kwargs
    extra = {'custom_fields': custom_fields}
    getattr(logger, level.lower())(message, extra=extra)
