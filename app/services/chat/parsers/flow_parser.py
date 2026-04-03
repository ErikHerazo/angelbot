import uuid
from app.services.chat.models.event import ChatEvent


def parse_zoho_flow_payload(body_json: dict) -> ChatEvent:
    lead_id = body_json.get("lead_id")
    phone = body_json.get("phone")
    email = body_json.get("email")
    first_name = body_json.get("first_name")
    last_name = body_json.get("last_name")

    session_id = (
        lead_id or phone or email or str(uuid.uuid4())
    )

    intent = (
        body_json.get("motivo_de_la_cita")
        or body_json.get("interes_formulario")
    )

    metadata = {
        **body_json,
        "channel": "flow"
    }

    return ChatEvent(
        source="flow",
        event_type="lead",
        session_id=session_id,
        request_id=str(uuid.uuid4()),
        lead_id=lead_id,
        user_name=f"{first_name} {last_name}" if first_name else None,
        user_email=email,
        user_phone=phone,
        message=intent,
        intent=intent,
        metadata=metadata,
        raw=body_json,
    )
