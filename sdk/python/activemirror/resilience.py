"""
Resilience & Performance Tools for ActiveMirrorOS

Provides error recovery middleware, circuit breakers, and performance profiling.

Usage:
    from activemirror.resilience import retry, CircuitBreaker, profile_performance

    @retry(max_attempts=3, backoff=2.0)
    def unreliable_operation():
        # This will retry up to 3 times with exponential backoff
        pass

    circuit = CircuitBreaker(failure_threshold=5, timeout=60)

    @profile_performance
    def slow_operation():
        # Performance will be logged
        pass

Author: AMOS Dev Twin
"""

import time
import functools
from typing import Callable, Any
from datetime import datetime, timedelta
from activemirror.logging import get_logger


logger = get_logger("resilience")


def retry(max_attempts: int = 3, backoff: float = 1.0, exceptions: tuple = (Exception,)):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff: Initial backoff time in seconds (doubles each retry)
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @retry(max_attempts=3, backoff=2.0)
        def unreliable_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_backoff = backoff

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1

                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            context={"error": str(e)},
                            exc_info=True,
                        )
                        raise

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}), retrying in {current_backoff}s",
                        context={"attempt": attempt, "backoff": current_backoff, "error": str(e)},
                    )

                    time.sleep(current_backoff)
                    current_backoff *= 2  # Exponential backoff

            return None

        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping operations that consistently fail.

    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, rejecting requests
    - HALF_OPEN: Testing if service recovered

    Example:
        circuit = CircuitBreaker(failure_threshold=5, timeout=60)

        @circuit.protect
        def call_external_service():
            pass
    """

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def protect(self, func: Callable) -> Callable:
        """Decorator to protect a function with circuit breaker."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if self.state == "OPEN":
                # Check if timeout has passed
                if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit breaker for {func.__name__} entering HALF_OPEN state")
                else:
                    logger.warning(f"Circuit breaker for {func.__name__} is OPEN, rejecting request")
                    raise Exception(f"Circuit breaker is OPEN for {func.__name__}")

            try:
                result = func(*args, **kwargs)

                # Success - reset failures
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failures = 0
                    logger.info(f"Circuit breaker for {func.__name__} recovered, entering CLOSED state")

                return result

            except Exception as e:
                self.failures += 1
                self.last_failure_time = datetime.now()

                if self.failures >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.error(
                        f"Circuit breaker for {func.__name__} opened after {self.failures} failures",
                        context={"threshold": self.failure_threshold},
                    )

                raise

        return wrapper


def profile_performance(func: Callable = None, *, log_threshold_ms: float = None):
    """
    Performance profiling decorator.

    Logs execution time and can alert on slow operations.

    Args:
        log_threshold_ms: Only log if execution time exceeds this threshold

    Example:
        @profile_performance
        def slow_operation():
            pass

        @profile_performance(log_threshold_ms=100)
        def another_operation():
            pass  # Only logged if takes >100ms
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                success = True
                return result

            except Exception as e:
                success = False
                raise

            finally:
                duration_ms = (time.time() - start_time) * 1000

                # Log if no threshold or if exceeded
                if log_threshold_ms is None or duration_ms >= log_threshold_ms:
                    logger.performance(
                        operation=func.__name__,
                        duration_ms=duration_ms,
                        context={
                            "success": success,
                            "module": func.__module__,
                        },
                    )

                # Record in metrics
                from activemirror.health import get_global_metrics
                metrics = get_global_metrics()
                metrics.record_operation(func.__name__, duration_ms, success)

        return wrapper

    # Handle both @profile_performance and @profile_performance(threshold=100)
    if func is None:
        return decorator
    else:
        return decorator(func)


class PerformanceContext:
    """
    Context manager for performance profiling.

    Example:
        with PerformanceContext("database_query") as perf:
            # Do work
            pass
        # perf.duration_ms available after context
    """

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        success = exc_type is None

        logger.performance(
            operation=self.operation_name,
            duration_ms=self.duration_ms,
            context={"success": success},
        )

        from activemirror.health import get_global_metrics
        metrics = get_global_metrics()
        metrics.record_operation(self.operation_name, self.duration_ms, success)


def graceful_degradation(fallback_value: Any = None, log_error: bool = True):
    """
    Graceful degradation decorator.

    Returns fallback value instead of raising exception.

    Example:
        @graceful_degradation(fallback_value=[])
        def get_recommendations():
            # If this fails, return []
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(
                        f"Function {func.__name__} failed, using fallback value",
                        context={"fallback": fallback_value, "error": str(e)},
                        exc_info=True,
                    )
                return fallback_value

        return wrapper
    return decorator
