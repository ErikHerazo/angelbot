from dataclasses import dataclass, field
from typing import Optional, Dict, List


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

    message_type: Optional[str] = None
    attachments: List[Dict] = field(default_factory=list)

    metadata: Dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    