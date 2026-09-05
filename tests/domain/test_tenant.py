from app.domain.entities.tenant import Tenant


def test_tenant_with_only_required_fields_has_expected_defaults():
    tenant = Tenant(
        tenant_id="agb",
        legal_name="Cosmetic Surgery BCN SLP",
        trade_name="Antiaging Group Barcelona",
        address="Ronda general Mitre 84",
        city="Barcelona",
        country="ES",
        tax_id="B63819130",
        timezone="Europe/Madrid",
    )

    assert tenant.is_active is True
    assert tenant.eu_vat_number is None
    assert tenant.contact_email is None
    assert tenant.subscription_plan is None


def test_tenant_accepts_all_optional_fields():
    tenant = Tenant(
        tenant_id="agb",
        legal_name="Cosmetic Surgery BCN SLP",
        trade_name="Antiaging Group Barcelona",
        address="Ronda general Mitre 84",
        city="Barcelona",
        country="ES",
        tax_id="B63819130",
        timezone="Europe/Madrid",
        eu_vat_number="ESB63819130",
        contact_email="admin@agb.example",
        contact_phone="+34600000000",
        default_currency="EUR",
        subscription_plan="pro",
        subscription_status="active",
        is_active=False,
    )

    assert tenant.eu_vat_number == "ESB63819130"
    assert tenant.subscription_status == "active"
    assert tenant.is_active is False
