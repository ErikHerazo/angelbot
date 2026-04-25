import json
from fastapi import Request
from app.core import security
from fastapi import HTTPException
from app.services.chat.parsers.salesiq_parser import parse_zoho_sales_payload
from app.services.chat.source_detector import detect_zoho_source
from app.services.chat.parsers.flow_parser import parse_zoho_flow_payload
from app.services.chat.chat_event_router import route_chat_event


async def dispatch_zoho_webhook(request: Request):
    try:
        headers = request.headers
        body_bytes = await request.body()

        source = detect_zoho_source(headers)

        # Validations
        if source == "salesiq":
            await security.validate_zoho_sales_webhook(request)
        elif source == "flow":
            await security.validate_zoho_flow_webhook(request)
        else:
            raise HTTPException(status_code=400, detail="Unknown Zoho source")

        body_json = json.loads(body_bytes)

        if source == "salesiq":
            event = parse_zoho_sales_payload(body_json)
        else:
            event = parse_zoho_flow_payload(body_json)

        return await route_chat_event(event)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    