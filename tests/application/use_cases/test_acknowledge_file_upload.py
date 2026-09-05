from app.application.use_cases.acknowledge_file_upload import AcknowledgeFileUpload


class FakeReplyLanguageResolver:
    def __init__(self, lang):
        self._lang = lang

    async def resolve(self, **kwargs):
        return self._lang


class FakeTranslator:
    def __init__(self):
        self.calls = []

    async def translate(self, text, *, from_lang, to_lang):
        self.calls.append((text, from_lang, to_lang))
        return f"[{to_lang}] {text}"


class FakeFileUploadAckConfig:
    async def get_message(self, tenant_id):
        return "Archivo subido con éxito."


def make_use_case(lang):
    return AcknowledgeFileUpload(
        reply_language_resolver=FakeReplyLanguageResolver(lang),
        translator=FakeTranslator(),
        file_upload_ack_config=FakeFileUploadAckConfig(),
    )


async def test_returns_untranslated_message_for_spanish():
    use_case = make_use_case(lang="es")

    result = await use_case.execute(tenant_id="agb", session_id="sess-1")

    assert result == "Archivo subido con éxito."


async def test_translates_message_for_other_languages():
    use_case = make_use_case(lang="en")

    result = await use_case.execute(tenant_id="agb", session_id="sess-1", visitor_language="en")

    assert result == "[en] Archivo subido con éxito."
