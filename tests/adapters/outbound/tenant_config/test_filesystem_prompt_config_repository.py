from app.adapters.outbound.tenant_config.filesystem_prompt_config_repository import (
    FilesystemPromptConfigRepository,
)


async def test_website_prompt_has_rules_substituted_and_reply_language_placeholder_intact():
    repository = FilesystemPromptConfigRepository(config_dir="app/config/tenants")

    prompt = await repository.get_base_prompt("agb", "website")

    assert "<<MINOR_SAFETY_RULE>>" not in prompt
    assert "<<DISAMBIGUATION_RULES>>" not in prompt
    assert "REGLA PRIORITARIA — MENORES DE 16 AÑOS" in prompt
    assert "REGLAS PRIORITARIAS DE DESAMBIGUACIÓN" in prompt
    assert "{reply_language}" in prompt


async def test_whatsapp_and_instagram_also_get_rules_substituted():
    repository = FilesystemPromptConfigRepository(config_dir="app/config/tenants")

    whatsapp_prompt = await repository.get_base_prompt("agb", "whatsapp")
    instagram_prompt = await repository.get_base_prompt("agb", "instagram")

    for prompt in (whatsapp_prompt, instagram_prompt):
        assert "<<MINOR_SAFETY_RULE>>" not in prompt
        assert "REGLA PRIORITARIA — MENORES DE 16 AÑOS" in prompt


async def test_flow_prompt_has_no_rule_blocks_injected():
    repository = FilesystemPromptConfigRepository(config_dir="app/config/tenants")

    prompt = await repository.get_base_prompt("agb", "flow")

    assert "REGLA PRIORITARIA — MENORES DE 16 AÑOS" not in prompt
    assert "REGLAS PRIORITARIAS DE DESAMBIGUACIÓN" not in prompt
    assert "{reply_language}" in prompt


async def test_unknown_channel_falls_back_to_website():
    repository = FilesystemPromptConfigRepository(config_dir="app/config/tenants")

    fallback_prompt = await repository.get_base_prompt("agb", "unknown-channel")
    website_prompt = await repository.get_base_prompt("agb", "website")

    assert fallback_prompt == website_prompt


async def test_prompt_can_be_formatted_with_reply_language():
    repository = FilesystemPromptConfigRepository(config_dir="app/config/tenants")

    prompt = await repository.get_base_prompt("agb", "website")
    formatted = prompt.format(reply_language="inglés")

    assert "{reply_language}" not in formatted
    assert "inglés" in formatted
