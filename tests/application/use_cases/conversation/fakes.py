class FakeLLM:
    """Returns queued responses in order, one per `.complete()` call.
    Each response is an LLMCompletion dict: {"content": ..., "tool_calls": ...}."""

    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, *, messages, tools=None, tool_choice=None):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        return self._responses.pop(0)


class FakeConversationHistory:
    def __init__(self, history: list[dict] | None = None):
        self._history = history or []

    async def get_history(self, tenant_id, session_id):
        return self._history

    async def append_turn(self, **kwargs):
        pass


class FakeReplyLanguageResolver:
    def __init__(self, language: str = "es"):
        self._language = language

    async def resolve(self, **kwargs):
        return self._language


class FakeReplyLanguageEnforcer:
    async def enforce(self, answer, reply_language):
        return answer


class FakeTranslation:
    async def translate(self, text, *, from_lang, to_lang):
        return text


class FakePromptConfig:
    async def get_base_prompt(self, tenant_id, channel):
        return "Eres un asistente. Responde en {reply_language}."


class FakeRetrievalTools:
    def __init__(self, call_result=None):
        self._call_result = call_result
        self.calls: list[tuple[str, dict]] = []

    async def get_tool_schemas(self):
        return [{"type": "function", "function": {"name": "search_price_catalog", "parameters": {}}}]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self._call_result


class FakeCheckBusinessAvailability:
    def __init__(self, available: bool):
        self._available = available

    async def execute(self, tenant_id):
        return self._available


class FakeCannedReplyConfig:
    def __init__(self, reply: str):
        self._reply = reply

    async def get_reply(self, tenant_id):
        return self._reply
