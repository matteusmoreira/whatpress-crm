from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Optional

from ..errors import ConfigError, ProviderNotFoundError
from .base import WhatsAppProvider


@dataclass(frozen=True)
class PluginSpec:
    provider_id: str
    import_path: str


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, WhatsAppProvider] = {}

    def register(self, provider: WhatsAppProvider) -> None:
        pid = provider.capabilities().provider_id.strip().lower()
        if not pid:
            raise ConfigError("provider_id inválido em provider.")
        self._providers[pid] = provider

    def get(self, provider_id: str) -> WhatsAppProvider:
        pid = str(provider_id or "").strip().lower()
        if pid in self._providers:
            return self._providers[pid]
        raise ProviderNotFoundError(pid)

    def list_provider_ids(self) -> list[str]:
        return sorted(self._providers.keys())

    def load_plugins(self, specs: list[PluginSpec]) -> None:
        for spec in specs:
            provider = _import_provider(spec.import_path)
            capabilities_id = provider.capabilities().provider_id.strip().lower()
            if capabilities_id and capabilities_id != spec.provider_id.strip().lower():
                raise ConfigError(
                    "Plugin provider_id diverge do spec.",
                    details={"spec": spec.provider_id, "capabilities": capabilities_id, "path": spec.import_path},
                )
            self.register(provider)


def _import_provider(path: str) -> WhatsAppProvider:
    raw = (path or "").strip()
    if ":" not in raw:
        raise ConfigError("Plugin import_path inválido (use modulo:objeto).", details={"import_path": raw})
    module_name, attr = raw.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        raise ConfigError("Falha ao importar módulo do plugin.", details={"module": module_name, "error": str(e)})
    if not hasattr(module, attr):
        raise ConfigError("Atributo do plugin não encontrado.", details={"module": module_name, "attr": attr})
    obj = getattr(module, attr)
    if callable(obj):
        return obj()
    return obj

