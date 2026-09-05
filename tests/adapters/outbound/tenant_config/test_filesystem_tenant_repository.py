import pytest

from app.adapters.outbound.tenant_config.filesystem_tenant_repository import (
    FilesystemTenantRepository,
)


async def test_reads_agb_tenant_from_real_config():
    repository = FilesystemTenantRepository(config_dir="app/config/tenants")

    tenant = await repository.get_tenant("agb")

    assert tenant.tenant_id == "agb"
    assert tenant.legal_name == "Cosmetic Surgery BCN SLP"
    assert tenant.trade_name == "Antiaging Group Barcelona"
    assert tenant.tax_id == "B63819130"
    assert tenant.eu_vat_number == "ESB63819130"
    assert tenant.timezone == "Europe/Madrid"
    assert tenant.is_active is True


async def test_reads_tenant_from_temp_config_dir(tmp_path):
    tenant_dir = tmp_path / "clienteb"
    tenant_dir.mkdir()
    (tenant_dir / "tenant.yaml").write_text(
        "tenant_id: clienteb\n"
        "legal_name: Cliente B SA\n"
        "trade_name: Cliente B\n"
        "address: Calle Falsa 123\n"
        "city: Bogotá\n"
        "country: CO\n"
        "tax_id: '900123456-7'\n"
        "timezone: America/Bogota\n"
    )
    repository = FilesystemTenantRepository(config_dir=str(tmp_path))

    tenant = await repository.get_tenant("clienteb")

    assert tenant.tenant_id == "clienteb"
    assert tenant.country == "CO"
    assert tenant.eu_vat_number is None


async def test_raises_when_tenant_config_missing(tmp_path):
    repository = FilesystemTenantRepository(config_dir=str(tmp_path))

    with pytest.raises(FileNotFoundError):
        await repository.get_tenant("does-not-exist")
