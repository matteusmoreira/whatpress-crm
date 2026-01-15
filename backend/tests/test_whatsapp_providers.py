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


def test_whatsapp_container_registers_evolution_provider() -> None:
    _ensure_backend_on_path()
    whatsapp = importlib.import_module("backend.whatsapp")
    container = whatsapp.get_whatsapp_container()
    provider_ids = set(container.registry.list_provider_ids())
    assert "evolution" in provider_ids


def test_whatsapp_container_registers_stub_providers() -> None:
    _ensure_backend_on_path()
    whatsapp = importlib.import_module("backend.whatsapp")
    container = whatsapp.get_whatsapp_container()
    provider_ids = set(container.registry.list_provider_ids())
    assert "uazapi" in provider_ids
    assert "wuzapi" in provider_ids
    assert "pastorini" in provider_ids
