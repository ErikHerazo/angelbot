from dataclasses import dataclass
from typing import Optional


@dataclass
class Tenant:
    tenant_id: str          # identificador técnico interno (slug o UUID)
    legal_name: str         # Razón Social
    trade_name: str         # Nombre comercial
    address: str            # Dirección
    city: str               # Ciudad
    country: str            # código ISO 3166-1 alpha-2, ej. "ES", "CO", "GB"
    tax_id: str             # CIF/NIF/NIT/VAT-equivalent según país (identificador de negocio)
    timezone: str           # ej. "Europe/Madrid" — usado por reglas de dominio como horario de atención
    eu_vat_number: Optional[str] = None  # VAT intracomunitario (solo aplica en UE)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    default_currency: Optional[str] = None   # ej. "EUR", "COP", "GBP"
    subscription_plan: Optional[str] = None  # ej. "basic", "pro", "enterprise"
    subscription_status: Optional[str] = None  # ej. "trial", "active", "suspended", "cancelled"
    is_active: bool = True
