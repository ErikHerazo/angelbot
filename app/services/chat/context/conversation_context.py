from dataclasses import dataclass
from typing import Optional


@dataclass
class ConversationContext:
    session_id: str
    conversation_id: str
    