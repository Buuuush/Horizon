"""Base scraper interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
import httpx
import asyncio

from ..models import ContentItem


class RetryConfig:
    """Configuration for retry logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_sec: float = 1.0,
        max_delay_sec: float = 10.0,
        exponential_base: float = 2.0,
        retry_on_status_codes: Optional[List[int]] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay_sec = base_delay_sec
        self.max_delay_sec = max_delay_sec
        self.exponential_base = exponential_base
        self.retry_on_status_codes = retry_on_status_codes or [408, 429, 500, 502, 503, 504]


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    # Default retry config for regular sources
    DEFAULT_RETRY_CONFIG = RetryConfig(max_attempts=3)

    # Extended retry config for flaky sources (Telegram, Twitter)
    FLAKY_RETRY_CONFIG = RetryConfig(max_attempts=5, base_delay_sec=2.0, max_delay_sec=30.0)

    def __init__(self, config: dict, http_client: httpx.AsyncClient, is_flaky: bool = False):
        """Initialize scraper.

        Args:
            config: Scraper-specific configuration
            http_client: Shared async HTTP client
            is_flaky: If True, use extended retry config for flaky sources
        """
        self.config = config
        self.client = http_client
        self.retry_config = self.FLAKY_RETRY_CONFIG if is_flaky else self.DEFAULT_RETRY_CONFIG
        self.consecutive_failures = 0
        self.is_circuit_broken = False

    @abstractmethod
    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch content items published since the given time.

        Args:
            since: Only fetch items published after this time

        Returns:
            List[ContentItem]: Fetched content items
        """
        pass

    async def _retry_with_backoff(
        self,
        async_func,
        *args,
        **kwargs
    ):
        """
        Retry an async function with exponential backoff.

        Args:
            async_func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result from async_func

        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None

        for attempt in range(1, self.retry_config.max_attempts + 1):
            try:
                result = await async_func(*args, **kwargs)
                # Success - reset circuit breaker
                self.consecutive_failures = 0
                self.is_circuit_broken = False
                return result

            except Exception as e:
                last_exception = e

                # Check if this is a retryable error
                is_retryable = False
                if isinstance(e, httpx.HTTPStatusError):
                    is_retryable = e.response.status_code in self.retry_config.retry_on_status_codes
                elif isinstance(e, (httpx.TimeoutException, httpx.ConnectError)):
                    is_retryable = True

                if not is_retryable or attempt == self.retry_config.max_attempts:
                    # Not retryable or final attempt
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= 3:
                        self.is_circuit_broken = True
                    raise

                # Calculate exponential backoff delay
                delay_sec = min(
                    self.retry_config.base_delay_sec * (self.retry_config.exponential_base ** (attempt - 1)),
                    self.retry_config.max_delay_sec,
                )

                print(
                    f"⚠ Retry {attempt}/{self.retry_config.max_attempts} after {delay_sec:.1f}s "
                    f"({type(e).__name__})"
                )

                await asyncio.sleep(delay_sec)

        raise last_exception

    def _generate_id(self, source_type: str, subtype: str, native_id: str) -> str:
        """Generate unique content item ID.

        Args:
            source_type: Source type (github, hackernews, etc.)
            subtype: Content subtype (event, release, story, etc.)
            native_id: Native ID from the source platform

        Returns:
            str: Unique ID in format {source}:{subtype}:{native_id}
        """
        return f"{source_type}:{subtype}:{native_id}"
