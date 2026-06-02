import logging
from app.core import constants
from datetime import datetime, timedelta, timezone
from openai import (
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError,
    BadRequestError,
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

        return datetime.now(timezone.utc) >= self.primary_retry_at

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

                return await request_callable(
                    secondary_client,
                    constants.DEPLOYMENT_NAME_SECONDARY
                )
            
            except BadRequestError as ex:
                logger.warning(
                    "PRIMARY BadRequestError. Switching to SECONDARY",
                    extra={
                        "error": str(ex)
                    }
                )
                self._block_primary(self.DEFAULT_COOLDOWN_SECONDS)
                return await request_callable(
                    secondary_client,
                    constants.DEPLOYMENT_NAME_SECONDARY
                )

            except (
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            ):

                self._block_primary(self.DEFAULT_COOLDOWN_SECONDS)

                return await request_callable(
                    secondary_client,
                    constants.DEPLOYMENT_NAME_SECONDARY
                )

        return await request_callable(
            secondary_client,
            constants.DEPLOYMENT_NAME_SECONDARY
        )


load_balancer = FailoverLoadBalancer()
