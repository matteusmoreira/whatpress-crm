from __future__ import annotations

import importlib
import sys
import asyncio
from pathlib import Path
from unittest import mock

import pytest


def _ensure_backend_on_path() -> None:
    here = Path(__file__).resolve()
    backend_dir = here.parent.parent
    root = backend_dir.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def test_uazapi_provider_registered_and_capabilities() -> None:
    _ensure_backend_on_path()
    whatsapp = importlib.import_module("backend.whatsapp")
    container = whatsapp.get_whatsapp_container()
    provider_ids = set(container.registry.list_provider_ids())
    assert "uazapi" in provider_ids
    provider = container.registry.get("uazapi")
    caps = provider.capabilities()
    assert caps.provider_id == "uazapi"
    assert "v1" in caps.supported_versions
    assert callable(getattr(provider, "send_presence", None))


def test_uazapi_parse_webhook_messages_upsert_fallback() -> None:
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
    _ensure_backend_on_path()
    uaz_mod = importlib.import_module("backend.whatsapp.providers.uazapi")
    base_mod = importlib.import_module("backend.whatsapp.providers.base")

    provider = uaz_mod.UazapiWhatsAppProvider(default_base_url="https://test.uazapi.com", default_admin_token="admin")
    conn_ref = base_mod.ConnectionRef(
        tenant_id="t1",
        provider="uazapi",
        instance_name="inst1",
        phone_number=None,
        config={"token": "tok1", "base_url": "https://test.uazapi.com"},
    )

    with mock.patch("backend.whatsapp.providers.uazapi._request_with_uazapi_fallbacks") as req_mock:
        req_mock.return_value = {"ok": True}
        result = asyncio.run(provider.send_presence(None, connection=conn_ref, phone="+55 (21) 99999-8888", presence="composing"))
        assert result == {"ok": True}

        assert req_mock.call_count == 1
        kwargs = req_mock.call_args.kwargs
        assert kwargs["method"] == "POST"
        assert kwargs["path"] == "/chat/updatePresence"
        assert kwargs["instance_name"] == "inst1"
        assert kwargs["json"] == {"number": "5521999998888", "presence": "composing"}


def test_uazapi_send_presence_rejects_empty_phone() -> None:
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
