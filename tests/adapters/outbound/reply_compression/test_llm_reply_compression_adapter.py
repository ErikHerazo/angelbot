from app.adapters.outbound.reply_compression.llm_reply_compression_adapter import (
    LLMReplyCompressionAdapter,
)


async def test_delegates_to_injected_compress_fn():
    calls = []

    async def fake_compress_fn(answer, original_question):
        calls.append((answer, original_question))
        return "short answer"

    adapter = LLMReplyCompressionAdapter(compress_fn=fake_compress_fn)

    result = await adapter.compress("a very long answer", "the question")

    assert result == "short answer"
    assert calls == [("a very long answer", "the question")]
