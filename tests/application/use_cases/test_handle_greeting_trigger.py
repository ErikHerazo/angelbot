from app.application.use_cases.handle_greeting_trigger import HandleGreetingTrigger


class FakeGreetingConfig:
    def __init__(self, greeting):
        self._greeting = greeting
        self.calls = []

    async def get_greeting(self, tenant_id):
        self.calls.append(tenant_id)
        return self._greeting


async def test_returns_the_tenants_greeting():
    use_case = HandleGreetingTrigger(greeting_config=FakeGreetingConfig("hola desde AGB"))

    result = await use_case.execute("agb")

    assert result == "hola desde AGB"
