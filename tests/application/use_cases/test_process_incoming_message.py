from app.application.use_cases.process_incoming_message import ProcessIncomingMessage


class FakeChatPlatform:
    def __init__(self):
        self.progress_calls = []
        self.final_calls = []

    async def send_progress_update(self, request_id):
        self.progress_calls.append(request_id)

    async def send_final_response(self, request_id, answer_text):
        self.final_calls.append((request_id, answer_text))


class FakeConversationEngine:
    def __init__(self, *, answer=None, raise_exception=None):
        self._answer = answer
        self._raise_exception = raise_exception
        self.calls = []

    async def generate_reply(self, *, tenant_id, session_id, user_question, channel, visitor_language=None):
        self.calls.append((tenant_id, session_id, user_question, channel, visitor_language))
        if self._raise_exception:
            raise self._raise_exception
        return self._answer


class FakeConversationHistory:
    def __init__(self):
        self.append_calls = []

    async def get_history(self, tenant_id, session_id):
        return []

    async def append_turn(self, *, tenant_id, session_id, user_message, assistant_message, max_history):
        self.append_calls.append((tenant_id, session_id, user_message, assistant_message, max_history))


class FakeReplyCompressor:
    def __init__(self, compressed_answer="compressed"):
        self._compressed_answer = compressed_answer
        self.calls = []

    async def compress(self, answer, original_question):
        self.calls.append((answer, original_question))
        return self._compressed_answer


def make_use_case(
    *,
    engine,
    chat_platform=None,
    history=None,
    compressor=None,
    channel_character_limits=None,
    stateless_channels=None,
):
    return ProcessIncomingMessage(
        chat_platform=chat_platform or FakeChatPlatform(),
        conversation_engine=engine,
        conversation_history=history or FakeConversationHistory(),
        reply_compressor=compressor or FakeReplyCompressor(),
        channel_character_limits=channel_character_limits or {},
        stateless_channels=stateless_channels or set(),
        fallback_message="fallback message",
        max_history=6,
    )


async def test_happy_path_delivers_generated_answer_and_saves_history():
    chat_platform = FakeChatPlatform()
    history = FakeConversationHistory()
    engine = FakeConversationEngine(answer="hi there")
    use_case = make_use_case(engine=engine, chat_platform=chat_platform, history=history)

    await use_case.execute(
        tenant_id="agb",
        request_id="req-1",
        session_id="sess-1",
        user_question="hello",
        channel="website",
    )

    assert chat_platform.progress_calls == ["req-1"]
    assert chat_platform.final_calls == [("req-1", "hi there")]
    assert history.append_calls == [("agb", "sess-1", "hello", "hi there", 6)]


async def test_falls_back_when_engine_raises():
    chat_platform = FakeChatPlatform()
    engine = FakeConversationEngine(raise_exception=RuntimeError("boom"))
    use_case = make_use_case(engine=engine, chat_platform=chat_platform)

    await use_case.execute(
        tenant_id="agb",
        request_id="req-1",
        session_id="sess-1",
        user_question="hello",
        channel="website",
    )

    assert chat_platform.final_calls == [("req-1", "fallback message")]


async def test_falls_back_when_engine_returns_empty_answer():
    chat_platform = FakeChatPlatform()
    engine = FakeConversationEngine(answer="")
    use_case = make_use_case(engine=engine, chat_platform=chat_platform)

    await use_case.execute(
        tenant_id="agb",
        request_id="req-1",
        session_id="sess-1",
        user_question="hello",
        channel="website",
    )

    assert chat_platform.final_calls == [("req-1", "fallback message")]


async def test_compresses_answer_when_over_channel_character_limit():
    chat_platform = FakeChatPlatform()
    compressor = FakeReplyCompressor(compressed_answer="short")
    engine = FakeConversationEngine(answer="this answer is definitely too long")
    use_case = make_use_case(
        engine=engine,
        chat_platform=chat_platform,
        compressor=compressor,
        channel_character_limits={"instagram": 5},
    )

    await use_case.execute(
        tenant_id="agb",
        request_id="req-1",
        session_id="sess-1",
        user_question="hello",
        channel="instagram",
    )

    assert compressor.calls == [("this answer is definitely too long", "hello")]
    assert chat_platform.final_calls == [("req-1", "short")]


async def test_does_not_save_history_for_stateless_channel():
    history = FakeConversationHistory()
    engine = FakeConversationEngine(answer="synthetic answer")
    use_case = make_use_case(
        engine=engine,
        history=history,
        stateless_channels={"flow"},
    )

    await use_case.execute(
        tenant_id="agb",
        request_id="req-1",
        session_id="sess-1",
        user_question="lead form question",
        channel="flow",
    )

    assert history.append_calls == []
