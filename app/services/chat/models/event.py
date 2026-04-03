from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class ChatEvent:
    source: str
    event_type: str
    
    session_id: str
    request_id: Optional[str] = None
    lead_id: Optional[str] = None

    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None

    message: Optional[str] = None
    intent: Optional[str] = None

    metadata: Dict = None
    raw: dict = None
    