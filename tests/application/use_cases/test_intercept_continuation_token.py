from app.application.use_cases.intercept_continuation_token import InterceptContinuationToken
from app.core import constants


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


class FakeContinueMessageConfig:
    async def get_message(self, tenant_id):
        return "Aquí sigo contigo"


def make_use_case(lang="es"):
    return InterceptContinuationToken(
        reply_language_resolver=FakeReplyLanguageResolver(lang),
        translator=FakeTranslator(),
        continue_message_config=FakeContinueMessageConfig(),
    )


async def test_returns_none_when_not_the_continue_token():
    use_case = make_use_case()

    result = await use_case.execute(
        tenant_id="agb",
        session_id="sess-1",
        user_question="hola, tengo una duda",
        channel="website",
    )

    assert result is None


async def test_returns_empty_string_for_flow_channel():
    use_case = make_use_case()

    result = await use_case.execute(
        tenant_id="agb",
        session_id="sess-1",
        user_question=constants.CONTINUE_TOKEN,
        channel="flow",
    )

    assert result == ""


async def test_returns_untranslated_message_when_language_is_spanish():
    use_case = make_use_case(lang="es")

    result = await use_case.execute(
        tenant_id="agb",
        session_id="sess-1",
        user_question=constants.CONTINUE_TOKEN,
        channel="website",
    )

    assert result == "Aquí sigo contigo"


async def test_translates_message_when_language_is_not_spanish():
    use_case = make_use_case(lang="en")

    result = await use_case.execute(
        tenant_id="agb",
        session_id="sess-1",
        user_question=constants.CONTINUE_TOKEN,
        channel="website",
    )

    assert result == "[en] Aquí sigo contigo"
