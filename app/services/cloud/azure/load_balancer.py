import logging
from app.core import constants
from datetime import datetime, timedelta, timezone
from openai import (
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError
)
from app.services.cloud.azure.client import primary_client, secondary_client


logger = logging.getLogger(__name__)


class FailoverLoadBalancer:
    DEFAULT_COOLDOWN_SECONDS = 15

    def __init__(self):
        self.primary_available = True
        self.primary_retry_at = None

    def _block_primary(self, seconds: int):
        self.primary_available = False
        self.primary_retry_at = (
            datetime.now(timezone.utc) + timedelta(seconds=seconds)
        )

        logger.warning(
            "PRIMARY blocked",
            extra={
                "cooldown_seconds": seconds,
                "retry_at": self.primary_retry_at.isoformat(),
            },
        )

    def _enable_primary(self):
        self.primary_available = True
        self.primary_retry_at = None

        logger.info("PRIMARY re-enabled")

    def _can_try_primary(self) -> bool:
        if self.primary_available:
            return True

        if self.primary_retry_at is None:
            return False

        if datetime.now(timezone.utc) >= self.primary_retry_at:
            self._enable_primary()
            return True

        return False

    def _extract_retry_after(self, error: RateLimitError) -> int:
        cooldown = self.DEFAULT_COOLDOWN_SECONDS

        try:
            response = getattr(error, "response", None)

            if not response:
                return cooldown

            retry_after = response.headers.get("retry-after")

            if retry_after:
                return max(1, int(float(retry_after)))

            retry_after_ms = response.headers.get("retry-after-ms")

            if retry_after_ms:
                return max(1, int(float(retry_after_ms) / 1000))

        except Exception:
            logger.exception("Failed to extract retry-after header")

        return cooldown

    async def execute(self, request_callable):

        if self._can_try_primary():

            try:
                return await request_callable(
                    primary_client,
                    constants.DEPLOYMENT_NAME_PRIMARY
                )

            except RateLimitError as ex:

                cooldown = self._extract_retry_after(ex)

                self._block_primary(cooldown)
                logger.warning(
                    "Failing over request to SECONDARY",
                    extra={
                        "reason": "RateLimitError",
                        "cooldown_seconds": cooldown,
                        "error": str(ex)
                    }
                )
                return await request_callable(
                    secondary_client,
                    constants.DEPLOYMENT_NAME_SECONDARY
                )

            except (
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            ) as ex:

                self._block_primary(self.DEFAULT_COOLDOWN_SECONDS)
                logger.warning(
                    "Failing over request to SECONDARY",
                    extra={
                        "reason": type(ex).__name__,
                        "error": str(ex)
                    }
                )
                return await request_callable(
                    secondary_client,
                    constants.DEPLOYMENT_NAME_SECONDARY
                )
        logger.info(
            "Using SECONDARY",
            extra={"reason": "primary_in_cooldown"}
        )
        return await request_callable(
            secondary_client,
            constants.DEPLOYMENT_NAME_SECONDARY
        )

load_balancer = FailoverLoadBalancer()
