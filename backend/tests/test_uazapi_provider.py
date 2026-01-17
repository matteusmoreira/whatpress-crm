from __future__ import annotations

import importlib
import sys
import asyncio
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient


def _ensure_backend_on_path() -> None:
    here = Path(__file__).resolve()
    backend_dir = here.parent.parent
    root = backend_dir.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def test_uazapi_provider_registered_and_capabilities() -> None:
    """Testa se o provider está registrado com capabilities v2."""
    _ensure_backend_on_path()
    whatsapp = importlib.import_module("backend.whatsapp")
    container = whatsapp.get_whatsapp_container()
    provider_ids = set(container.registry.list_provider_ids())
    assert "uazapi" in provider_ids
    provider = container.registry.get("uazapi")
    caps = provider.capabilities()
    assert caps.provider_id == "uazapi"
    # UAZAPI v2
    assert "v2" in caps.supported_versions
    assert callable(getattr(provider, "send_presence", None))


def test_uazapi_parse_webhook_messages_upsert_fallback() -> None:
    """Testa o parse de webhooks de mensagem com fallback."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    EvolutionAPI = uaz_mod.EvolutionAPI

    original_parse = EvolutionAPI.parse_webhook_message

    def fake_parse(self, payload):
        raise Exception("boom")

    EvolutionAPI.parse_webhook_message = fake_parse
    try:
        provider = uaz_mod.UazapiWhatsAppProvider()
        payload = {
            "instance_uuid": "78167818-852a-413a-ad14-57c6942705a8",
            "event": "messages.upsert",
            "date_time": "2025-02-16T14:30:25.123Z",
            "data": {
                "type": "conversation",
                "message": "Olá, tudo bem?",
                "sender": "5598987654321",
                "pushname": "José",
            },
        }
        event = provider.parse_webhook(None, payload)
        assert event.event == "message"
        assert event.instance == "78167818-852a-413a-ad14-57c6942705a8"
        data = event.data
        assert data.get("content") == "Olá, tudo bem?"
        assert data.get("remote_jid") == "5598987654321"
    finally:
        EvolutionAPI.parse_webhook_message = original_parse


def test_uazapi_parse_webhook_presence_update_fallback() -> None:
    """Testa o parse de webhooks de presença com fallback."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    EvolutionAPI = uaz_mod.EvolutionAPI

    original_parse = EvolutionAPI.parse_webhook_message

    def fake_parse(self, payload):
        raise Exception("boom")

    EvolutionAPI.parse_webhook_message = fake_parse
    try:
        provider = uaz_mod.UazapiWhatsAppProvider()
        payload = {
            "instance_uuid": "78167818-852a-413a-ad14-57c6942705a8",
            "event": "presence.update",
            "data": {
                "presences": [
                    {"id": "5598987654321@s.whatsapp.net", "presence": "composing"},
                ]
            },
        }
        event = provider.parse_webhook(None, payload)
        assert event.event == "presence"
        assert event.instance == "78167818-852a-413a-ad14-57c6942705a8"
        data = event.data
        assert data.get("remote_jid") == "5598987654321"
        assert data.get("presence") == "composing"
    finally:
        EvolutionAPI.parse_webhook_message = original_parse


def test_uazapi_send_presence_formats_phone_and_calls_request() -> None:
    """Testa se send_presence formata telefone e usa endpoint v2 correto."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    base_mod = importlib.import_module("backend.whatsapp.providers.base")
    http_mod = importlib.import_module("backend.whatsapp.http")

    provider = uaz_mod.UazapiWhatsAppProvider(default_base_url="https://test.uazapi.com", default_admin_token="admin")
    conn_ref = base_mod.ConnectionRef(
        tenant_id="t1",
        provider="uazapi",
        instance_name="inst1",
        phone_number=None,
        config={"token": "tok1", "base_url": "https://test.uazapi.com"},
    )

    with mock.patch.object(http_mod.HttpClient, "request") as req_mock:
        async def mock_request(*args, **kwargs):
            return {"ok": True}
        req_mock.side_effect = mock_request
        result = asyncio.run(provider.send_presence(None, connection=conn_ref, phone="+55 (21) 99999-8888", presence="composing"))
        assert result == {"ok": True}

        assert req_mock.call_count == 1
        # Verificar chamada: POST /message/presence (v2)
        call_args = req_mock.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/message/presence"
        assert call_args[1]["json"] == {"number": "5521999998888", "presence": "composing"}


def test_uazapi_send_presence_rejects_empty_phone() -> None:
    """Testa que send_presence rejeita telefone vazio."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    base_mod = importlib.import_module("backend.whatsapp.providers.base")
    errors_mod = importlib.import_module("backend.whatsapp.errors")

    provider = uaz_mod.UazapiWhatsAppProvider(default_base_url="https://test.uazapi.com", default_admin_token="admin")
    conn_ref = base_mod.ConnectionRef(
        tenant_id="t1",
        provider="uazapi",
        instance_name="inst1",
        phone_number=None,
        config={"token": "tok1", "base_url": "https://test.uazapi.com"},
    )

    with pytest.raises(errors_mod.ProviderRequestError):
        asyncio.run(provider.send_presence(None, connection=conn_ref, phone="", presence="composing"))


def test_uazapi_send_text_message() -> None:
    """Testa envio de mensagem de texto via endpoint v2."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    base_mod = importlib.import_module("backend.whatsapp.providers.base")
    http_mod = importlib.import_module("backend.whatsapp.http")

    provider = uaz_mod.UazapiWhatsAppProvider(default_base_url="https://test.uazapi.com", default_admin_token="admin")
    conn_ref = base_mod.ConnectionRef(
        tenant_id="t1",
        provider="uazapi",
        instance_name="inst1",
        phone_number=None,
        config={"token": "tok1", "base_url": "https://test.uazapi.com"},
    )

    from backend.whatsapp.providers.base import SendMessageRequest
    req = SendMessageRequest(
        instance_name="inst1",
        phone="5511999999999",
        kind="text",
        content="Olá, mundo!",
        caption=None,
        filename=None,
    )

    with mock.patch.object(http_mod.HttpClient, "request") as req_mock:
        async def mock_request(*args, **kwargs):
            return {"success": True, "id": "msg123"}
        req_mock.side_effect = mock_request
        result = asyncio.run(provider.send_message(None, connection=conn_ref, req=req))

        assert result["success"] is True
        # Verificar chamada: POST /send/text (v2)
        call_args = req_mock.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/send/text"
        assert call_args[1]["json"] == {"number": "5511999999999", "text": "Olá, mundo!"}


def test_uazapi_send_media_message() -> None:
    """Testa envio de mídia via endpoint v2."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    base_mod = importlib.import_module("backend.whatsapp.providers.base")
    http_mod = importlib.import_module("backend.whatsapp.http")

    provider = uaz_mod.UazapiWhatsAppProvider(default_base_url="https://test.uazapi.com", default_admin_token="admin")
    conn_ref = base_mod.ConnectionRef(
        tenant_id="t1",
        provider="uazapi",
        instance_name="inst1",
        phone_number=None,
        config={"token": "tok1", "base_url": "https://test.uazapi.com"},
    )

    from backend.whatsapp.providers.base import SendMessageRequest
    req = SendMessageRequest(
        instance_name="inst1",
        phone="5511999999999",
        kind="image",
        content="https://example.com/image.jpg",
        caption="Uma imagem",
        filename=None,
    )

    with mock.patch.object(http_mod.HttpClient, "request") as req_mock:
        async def mock_request(*args, **kwargs):
            return {"success": True, "id": "msg456"}
        req_mock.side_effect = mock_request
        result = asyncio.run(provider.send_message(None, connection=conn_ref, req=req))

        assert result["success"] is True
        # Verificar chamada: POST /send/media (v2)
        call_args = req_mock.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/send/media"
        expected_json = {
            "number": "5511999999999",
            "type": "image",
            "file": "https://example.com/image.jpg",
            "text": "Uma imagem"
        }
        assert call_args[1]["json"] == expected_json


def test_uazapi_client_uses_token_header() -> None:
    """Testa que o cliente usa header 'token' (v2)."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    base_mod = importlib.import_module("backend.whatsapp.providers.base")

    provider = uaz_mod.UazapiWhatsAppProvider(default_base_url="https://test.uazapi.com", default_admin_token="admin")
    conn_ref = base_mod.ConnectionRef(
        tenant_id="t1",
        provider="uazapi",
        instance_name="inst1",
        phone_number=None,
        config={"token": "my_instance_token", "base_url": "https://test.uazapi.com"},
    )

    client, cfg = provider._build_client(conn_ref)

    # Verificar que o auth tem o header 'token' (dataclass usa .headers, não ._headers)
    assert hasattr(client, "_auth")
    assert client._auth.headers.get("token") == "my_instance_token"


def test_uazapi_admin_client_uses_admintoken_header() -> None:
    """Testa que o cliente admin usa header 'admintoken' (v2)."""
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    base_mod = importlib.import_module("backend.whatsapp.providers.base")

    provider = uaz_mod.UazapiWhatsAppProvider(default_base_url="https://test.uazapi.com", default_admin_token="default_admin")
    conn_ref = base_mod.ConnectionRef(
        tenant_id="t1",
        provider="uazapi",
        instance_name="inst1",
        phone_number=None,
        config={"admintoken": "my_admin_token", "base_url": "https://test.uazapi.com"},
    )

    client, cfg = provider._build_admin_client(conn_ref)

    # Verificar que o auth tem o header 'admintoken' (dataclass usa .headers, não ._headers)
    assert hasattr(client, "_auth")
    assert client._auth.headers.get("admintoken") == "my_admin_token"


def test_server_webhook_uazapi_accepts_suffix_and_injects_event_and_type() -> None:
    _ensure_backend_on_path()
    srv = importlib.import_module("backend.server")

    srv._ensure_offline_flush_task_started = lambda: None
    srv._ensure_bulk_worker_task_started = lambda: None

    called = []

    async def fake_uazapi(instance_name: str, payload: dict, *, from_queue: bool) -> dict:
        called.append((instance_name, payload, from_queue))
        return {"success": True}

    original = srv._process_uazapi_webhook
    srv._process_uazapi_webhook = fake_uazapi
    try:
        with TestClient(srv.app) as client:
            resp = client.post(
                "/api/webhooks/uazapi/onebarber/messages/conversation",
                json={"data": {}},
            )
            assert resp.status_code == 200
    finally:
        srv._process_uazapi_webhook = original

    assert len(called) == 1
    instance_name, payload, from_queue = called[0]
    assert instance_name == "onebarber"
    assert from_queue is False
    assert payload.get("event") == "messages"
    assert isinstance(payload.get("data"), dict)
    assert payload["data"].get("type") == "conversation"


def test_server_webhook_uazapi_accepts_batch_payload_list() -> None:
    _ensure_backend_on_path()
    srv = importlib.import_module("backend.server")

    srv._ensure_offline_flush_task_started = lambda: None
    srv._ensure_bulk_worker_task_started = lambda: None

    calls = []

    async def fake_uazapi(instance_name: str, payload: dict, *, from_queue: bool) -> dict:
        calls.append((instance_name, payload, from_queue))
        return {"success": True}

    original = srv._process_uazapi_webhook
    srv._process_uazapi_webhook = fake_uazapi
    try:
        with TestClient(srv.app) as client:
            resp = client.post(
                "/api/webhooks/uazapi/onebarber",
                json=[{"event": "messages"}, {"event": "presence"}],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("batch") is True
            assert data.get("count") == 2
    finally:
        srv._process_uazapi_webhook = original

    assert len(calls) == 2


def test_flush_db_queue_routes_webhook_event_to_uazapi_processor() -> None:
    _ensure_backend_on_path()
    srv = importlib.import_module("backend.server")

    called_uazapi = []
    called_evolution = []

    async def fake_uazapi(instance_name: str, payload: dict, *, from_queue: bool) -> dict:
        called_uazapi.append((instance_name, payload, from_queue))
        return {"success": True}

    async def fake_evolution(instance_name: str, payload: dict, *, from_queue: bool) -> dict:
        called_evolution.append((instance_name, payload, from_queue))
        return {"success": True}

    original_uazapi = srv._process_uazapi_webhook
    original_evolution = srv._process_evolution_webhook
    try:
        srv._process_uazapi_webhook = fake_uazapi
        srv._process_evolution_webhook = fake_evolution
        srv._DB_WRITE_QUEUE.clear()
        srv._DB_WRITE_QUEUE.append({
            "kind": "webhook_event",
            "provider": "uazapi",
            "instance_name": "onebarber",
            "payload": {"event": "messages"},
        })

        processed = asyncio.run(srv._flush_db_write_queue_once())
        assert processed == 1
    finally:
        srv._process_uazapi_webhook = original_uazapi
        srv._process_evolution_webhook = original_evolution
        srv._DB_WRITE_QUEUE.clear()

    assert len(called_uazapi) == 1
    assert len(called_evolution) == 0
