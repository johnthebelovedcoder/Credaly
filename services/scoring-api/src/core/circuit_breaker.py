"""
Circuit Breaker — prevents cascading failures when external APIs are down.
Per PRD FR-010: graceful degradation when a single source fails.

Usage:
    breaker = CircuitBreaker(name="crc_bureau", failure_threshold=5, recovery_timeout=60)

    async with breaker:
        result = await external_api.fetch()
"""

import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing — reject requests immediately
    HALF_OPEN = "half_open" # Testing recovery — allow one request through


class CircuitBreakerError(Exception):
    """Raised when the circuit is OPEN and the request is rejected."""
    pass


class CircuitBreaker:
    """
    State machine:
      CLOSED → OPEN: after `failure_threshold` consecutive failures
      OPEN → HALF_OPEN: after `recovery_timeout` seconds
      HALF_OPEN → CLOSED: on first success
      HALF_OPEN → OPEN: on first failure
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if (
                self._last_failure_time is not None
                and time.time() - self._last_failure_time >= self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker transitioning to HALF_OPEN",
                    circuit=self.name,
                )
        return self._state

    async def __aenter__(self):
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN — "
                f"external service is unavailable. Try again later."
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Request failed
            self._failure_count += 1
            self._last_failure_time = time.time()
            logger.warning(
                "Circuit breaker failure",
                circuit=self.name,
                failure_count=self._failure_count,
                error=str(exc_val),
            )
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(
                    "Circuit breaker OPEN — threshold reached",
                    circuit=self.name,
                    threshold=self.failure_threshold,
                )
            # Don't suppress the exception — let it propagate
            return False
        else:
            # Request succeeded
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(
                    "Circuit breaker recovered → CLOSED",
                    circuit=self.name,
                )
            self._failure_count = 0
            return False

    def reset(self):
        """Manually reset the circuit breaker (e.g., after admin intervention)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        logger.info("Circuit breaker manually reset", circuit=self.name)

    def get_status(self) -> dict:
        """Return current circuit breaker status for health checks."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# ── Registry ─────────────────────────────────────────────────────────────

_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=5,
            recovery_timeout=60,
        )
    return _breakers[name]


def get_all_breakers() -> dict[str, CircuitBreaker]:
    """Return all registered circuit breakers."""
    return dict(_breakers)
