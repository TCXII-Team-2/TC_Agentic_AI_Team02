import asyncio
import time
from functools import wraps
from typing import Callable, Any, Optional, TypeVar, Coroutine
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """States of the circuit breaker."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreakerError(Exception):
    """Exception raised when circuit is open."""
    pass

class CircuitBreaker:
    """Circuit breaker pattern implementation with retry logic."""
    
    def __init__(
        self,
        max_failures: int = 3,
        timeout: int = 60,
        name: str = "circuit_breaker"
    ):
        self.max_failures = max_failures
        self.timeout = timeout
        self.name = name
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open state."""
        if self.state != CircuitState.OPEN:
            return False
        
        if self.last_failure_time is None:
            return False
        
        return (time.time() - self.last_failure_time) >= self.timeout
    
    def record_success(self) -> None:
        """Record a successful operation."""
        self.failure_count = 0
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info(f"Circuit {self.name} recovered to CLOSED state")
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.max_failures:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} opened after {self.failure_count} failures")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            logger.info(f"Circuit {self.name} entering HALF_OPEN state for recovery test")
        
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(f"Circuit {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    async def call_async(self, func: Callable[..., Coroutine], *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        if self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            logger.info(f"Circuit {self.name} entering HALF_OPEN state for recovery test")
        
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(f"Circuit {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 1.0):
    """Decorator for retrying with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}, "
                            f"retrying in {wait_time}s. Error: {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}. "
                            f"Final error: {str(e)}"
                        )
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}, "
                            f"retrying in {wait_time}s. Error: {str(e)}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}. "
                            f"Final error: {str(e)}"
                        )
            
            raise last_exception
        
        # Return async or sync wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

async def retry_with_fallback(
    primary_func: Callable[..., Coroutine],
    fallback_func: Callable[..., Coroutine],
    max_retries: int = 3,
    fallback_message: str = "Fallback response"
) -> Any:
    """Try primary function with retries, fall back to secondary on failure."""
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await primary_func()
        except Exception as e:
            last_exception = e
            logger.warning(f"Primary attempt {attempt + 1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    
    logger.warning(f"All {max_retries} primary attempts failed, using fallback")
    try:
        result = await fallback_func()
        logger.info(f"Fallback successful: {fallback_message}")
        return result
    except Exception as e:
        logger.error(f"Fallback also failed: {str(e)}")
        raise Exception(f"Both primary and fallback failed. Last error: {str(last_exception)}")
