import asyncio
import os

import yaml


class FilesystemPromptConfigRepository:
    """Implements PromptConfigRepositoryPort, reading channel prompt
    templates + the shared safety/disambiguation rule blocks from
    config/tenants/{tenant_id}/prompts/.

    Mirrors the legacy constants.py composition (base template with
    `<<MINOR_SAFETY_RULE>>`/`<<DISAMBIGUATION_RULES>>` placeholders,
    `.replace()`-substituted, `{reply_language}` left in place for the
    caller to `.format()` per turn) -- but as data files instead of Python
    string literals, so this is per-tenant.

    Channel templates are YAML (`{channel}.yaml`, a `template:` key) --
    engineering-owned prompt-engineering artifacts, structured for easier
    future use with LangChain's native YAML prompt loading (see the
    upcoming LangGraph/LangChain migration). The two rule blocks are
    Markdown (`minor_safety_rule.md`, `disambiguation_rules.md`) instead --
    they're maintained by business/legal from external plain-text sources
    (see agb_documentos_desambiguacion_fuente memory), and Markdown avoids
    YAML's quoting/escaping rules tripping up a non-technical editor.

    The two `.replace()` calls are unconditional and simply no-op for a
    channel template (e.g. flow.yaml) that doesn't contain those tokens,
    matching the legacy exclusion of "flow" without hardcoding that channel
    name here.
    """

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_base_prompt(self, tenant_id: str, channel: str) -> str:
        return await asyncio.to_thread(self._read_base_prompt, tenant_id, channel)

    def _read_base_prompt(self, tenant_id: str, channel: str) -> str:
        prompts_dir = os.path.join(self._config_dir, tenant_id, "prompts")

        channel_path = os.path.join(prompts_dir, f"{channel}.yaml")
        if not os.path.exists(channel_path):
            channel_path = os.path.join(prompts_dir, "website.yaml")  # legacy fallback

        template = self._read_template(channel_path)
        minor_safety_rule = self._read_markdown(os.path.join(prompts_dir, "minor_safety_rule.md"))
        disambiguation_rules = self._read_markdown(os.path.join(prompts_dir, "disambiguation_rules.md"))

        return (
            template
            .replace("<<MINOR_SAFETY_RULE>>", minor_safety_rule)
            .replace("<<DISAMBIGUATION_RULES>>", disambiguation_rules)
        )

    @staticmethod
    def _read_template(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data["template"].strip()

    @staticmethod
    def _read_markdown(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
