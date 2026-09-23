import asyncio
import os


class FilesystemMinorPatientDeferralConfigRepository:
    """Implements MinorPatientDeferralConfigRepositoryPort, reading
    minor_patient_deferral_message.txt from config/tenants/{tenant_id}/ --
    same plain-text, one-concern-per-file pattern as agenda_reply.txt/
    pectus_poland_disambiguation_question.txt."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_reply(self, tenant_id: str) -> str:
        return await asyncio.to_thread(self._read_reply, tenant_id)

    def _read_reply(self, tenant_id: str) -> str:
        path = os.path.join(self._config_dir, tenant_id, "minor_patient_deferral_message.txt")

        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
