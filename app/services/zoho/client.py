import httpx
import logging
from app.core import constants
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ZohoClient:
    def __init__(self, access_token: str):
        self.headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }

    async def _post(self, url: str, payload: dict, timeout: float = 10.0):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=self.headers)
        except httpx.RequestError as e:
            logger.error(
                "Zoho connection error",
                extra={
                    "url": url,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=502,
                detail=f"Zoho connection error: {str(e)}"
            )

        if resp.status_code not in (200, 204):
            logger.error(
                "Zoho API error",
                extra={
                    "url": url,
                    "status": resp.status_code,
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Zoho API error {resp.status_code}: {resp.text}"
            )

    # ---------------------------------------------------------------------
    # ✔️ function to send the final response via API callback/response
    # ---------------------------------------------------------------------
    async def send_progress_update(self, request_id: str):
        """Send a 'progress' message to extend Zoho's timeout."""

        url = f"https://{constants.ZOHOSALESIQ_SERVER_URI}/api/v2/{constants.SCREENNAME}/callbacks/{request_id}/progress"
        
        payload = {
            "text": "Just a few more seconds.."
        }

        await self._post(url=url, payload=payload)

        logger.info(
            "Zoho progress sent",
            extra={"request_id": request_id},
        )
    
    async def send_final_response(self, request_id: str, answer_text: str):
        """Envia la respuesta final a Zoho para completar la acción pendiente."""
        url = f"https://{constants.ZOHOSALESIQ_SERVER_URI}/api/v2/{constants.SCREENNAME}/callbacks/{request_id}/response"

        payload = {
            "action":"reply",
            "replies": [
                {
                    "text": answer_text
                }
            ]
        }
        
        await self._post(url=url, payload=payload, timeout=30.0)

        logger.info(
            "Zoho final response sent",
            extra={"request_id": request_id},
        )
        