from dataclasses import dataclass
from typing import Optional


@dataclass
class LeadSubmission:
    first_name: str
    last_name: str
    lang: str
    reason_for_appointment: Optional[str]
    form_interest: Optional[str]

    @property
    def combined_intent(self) -> Optional[str]:
        parts = [p for p in (self.reason_for_appointment, self.form_interest) if p]
        return " | ".join(parts) if parts else None

    def build_synthetic_question(self) -> str:
        return f"Motivo de consulta del paciente: {self.combined_intent}. Idioma: {self.lang}."
