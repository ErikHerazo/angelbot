from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web.routes import chat_test_hexagonal as module


def make_client(secret):
    module.CHAT_TEST_SECRET = secret
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def test_returns_404_when_secret_not_configured():
    client = make_client(secret=None)

    response = client.post("/test-hexagonal", json={"message": "hola"})

    assert response.status_code == 404


def test_returns_401_when_secret_header_is_wrong():
    client = make_client(secret="the-real-secret")

    response = client.post(
        "/test-hexagonal",
        json={"message": "hola"},
        headers={"X-Test-Secret": "wrong"},
    )

    assert response.status_code == 401


def test_success_path_returns_answer_captured_from_process_incoming_message(monkeypatch):
    client = make_client(secret="the-real-secret")

    class FakeUseCase:
        async def execute(self, *, tenant_id, request_id, session_id, user_question, channel, visitor_language=None):
            await captured_chat_platform.send_final_response(request_id, f"echo: {user_question}")

    captured_chat_platform = None

    async def fake_build_process_incoming_message(tenant_id, *, chat_platform):
        nonlocal captured_chat_platform
        captured_chat_platform = chat_platform
        return FakeUseCase()

    monkeypatch.setattr(module, "build_process_incoming_message", fake_build_process_incoming_message)

    response = client.post(
        "/test-hexagonal",
        json={"message": "hola", "channel": "website"},
        headers={"X-Test-Secret": "the-real-secret"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "echo: hola"
    assert data["session_id"].startswith("test-")


def test_reuses_provided_session_id(monkeypatch):
    client = make_client(secret="the-real-secret")

    class FakeUseCase:
        async def execute(self, *, tenant_id, request_id, session_id, user_question, channel, visitor_language=None):
            await chat_platform_holder["cp"].send_final_response(request_id, "ok")

    chat_platform_holder = {}

    async def fake_build_process_incoming_message(tenant_id, *, chat_platform):
        chat_platform_holder["cp"] = chat_platform
        return FakeUseCase()

    monkeypatch.setattr(module, "build_process_incoming_message", fake_build_process_incoming_message)

    response = client.post(
        "/test-hexagonal",
        json={"message": "hola", "session_id": "sess-fixed"},
        headers={"X-Test-Secret": "the-real-secret"},
    )

    assert response.json()["session_id"] == "sess-fixed"
