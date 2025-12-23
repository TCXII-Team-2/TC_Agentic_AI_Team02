"""Utilities for observability, monitoring, and error handling."""

from .logging_config import (
    setup_logging,
    generate_trace_id,
    set_trace_id,
    get_trace_id,
    log_with_context,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    retry_with_backoff,
    retry_with_fallback,
)
from .monitoring import (
    Metrics,
    Tracer,
    AlertManager,
    get_metrics,
    get_alert_manager,
)

__all__ = [
    "setup_logging",
    "generate_trace_id",
    "set_trace_id",
    "get_trace_id",
    "log_with_context",
    "CircuitBreaker",
    "CircuitBreakerError",
    "retry_with_backoff",
    "retry_with_fallback",
    "Metrics",
    "Tracer",
    "AlertManager",
    "get_metrics",
    "get_alert_manager",
]
