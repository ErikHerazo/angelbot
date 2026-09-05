from app.adapters.inbound.zoho.greeting_trigger_handler import ZohoGreetingTriggerHandler


class FakeUseCase:
    def __init__(self, greeting):
        self._greeting = greeting

    async def execute(self, tenant_id):
        return self._greeting


async def test_formats_greeting_as_zoho_reply_payload():
    handler = ZohoGreetingTriggerHandler(use_case=FakeUseCase("hola"), tenant_id="agb")

    result = await handler.handle()

    assert result == {"action": "reply", "replies": [{"text": "hola"}]}
