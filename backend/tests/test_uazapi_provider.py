from __future__ import annotations

import importlib
import sys
from pathlib import Path


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

