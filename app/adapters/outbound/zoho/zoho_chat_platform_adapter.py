import logging

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ZohoChatPlatformAdapter:
    """Implements ChatPlatformPort for Zoho SalesIQ callbacks."""

    def __init__(self, *, access_token: str, server_uri: str, screenname: str):
        self._server_uri = server_uri
        self._screenname = screenname
        self._headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json",
        }

    async def _post(self, url: str, payload: dict, timeout: float = 10.0):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
        except httpx.RequestError as e:
            logger.error("Zoho connection error", extra={"url": url, "error": str(e)})
            raise HTTPException(status_code=502, detail=f"Zoho connection error: {str(e)}")

        if resp.status_code not in (200, 204):
            logger.error("Zoho API error", extra={"url": url, "status": resp.status_code})
            raise HTTPException(
                status_code=500,
                detail=f"Zoho API error {resp.status_code}: {resp.text}",
            )

    async def send_progress_update(self, request_id: str) -> None:
        """Send a 'progress' message to extend Zoho's timeout."""
        url = f"https://{self._server_uri}/api/v2/{self._screenname}/callbacks/{request_id}/progress"
        payload = {"text": "Just a few more seconds.."}

        await self._post(url=url, payload=payload)

        logger.info("Zoho progress sent", extra={"request_id": request_id})

    async def send_final_response(self, request_id: str, answer_text: str) -> None:
        """Envia la respuesta final a Zoho para completar la acción pendiente."""
        url = f"https://{self._server_uri}/api/v2/{self._screenname}/callbacks/{request_id}/response"
        payload = {
            "action": "reply",
            "replies": [{"text": answer_text}],
        }

        await self._post(url=url, payload=payload, timeout=30.0)

        logger.info("Zoho final response sent", extra={"request_id": request_id})
