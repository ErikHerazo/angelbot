from app.application.use_cases.handle_greeting_trigger import HandleGreetingTrigger


class ZohoGreetingTriggerHandler:
    """Formats HandleGreetingTrigger's result as a Zoho SalesIQ webhook
    reply -- same response shape as the legacy trigger_handler.handle_trigger.

    Known, unfixed limitation carried over from the legacy handler: the
    greeting isn't translated to the visitor's language -- the "trigger"
    event's call site (chat_event_router.py) doesn't thread visitor_language
    through today. Not fixed here (would mean touching that call site,
    beyond porting this handler); flagged for Erik to decide on separately.
    """

    def __init__(self, *, use_case: HandleGreetingTrigger, tenant_id: str):
        self._use_case = use_case
        self._tenant_id = tenant_id

    async def handle(self) -> dict:
        greeting = await self._use_case.execute(self._tenant_id)

        return {
            "action": "reply",
            "replies": [{"text": greeting}],
        }
