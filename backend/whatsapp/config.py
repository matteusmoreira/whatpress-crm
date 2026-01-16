from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Protocol

    class YAMLValidationError(Exception):
        pass

    class _YamlDoc(Protocol):
        data: Any

    def load_yaml(_text: str) -> _YamlDoc:
        raise NotImplementedError
else:
    from strictyaml import YAMLValidationError, load as load_yaml

from .errors import ConfigError
from .providers.registry import PluginSpec


@dataclass(frozen=True)
class WhatsAppConfig:
    plugins: list[PluginSpec]
    dev_sandbox_enabled: bool = False


def load_whatsapp_config() -> WhatsAppConfig:
    inline = (os.getenv("WHATSAPP_PROVIDERS_CONFIG_INLINE") or "").strip()
    path = (os.getenv("WHATSAPP_PROVIDERS_CONFIG") or "").strip()
    dev = (os.getenv("WHATSAPP_DEV_SANDBOX") or "").strip().lower() in {"1", "true", "yes", "y"}

    if inline:
        data = _parse_text(inline)
    elif path:
        data = _parse_file(path)
    else:
        data = {}

    plugins = _parse_plugins(data)
    return WhatsAppConfig(plugins=plugins, dev_sandbox_enabled=dev)


def _parse_file(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        raise ConfigError("Falha ao ler arquivo de configuração.", details={"path": path, "error": str(e)})
    return _parse_text(text, source=path)


def _parse_text(text: str, source: str = "inline") -> dict[str, Any]:
    raw = (text or "").lstrip()
    if not raw:
        return {}
    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
        except Exception as e:
            raise ConfigError("JSON inválido em configuração.", details={"source": source, "error": str(e)})
        if isinstance(data, dict):
            return data
        return {"plugins": data}
    try:
        y = load_yaml(raw)
        data = y.data
    except YAMLValidationError as e:
        raise ConfigError("YAML inválido em configuração.", details={"source": source, "error": str(e)})
    if isinstance(data, dict):
        return data
    return {"plugins": data}


def _parse_plugins(data: dict[str, Any]) -> list[PluginSpec]:
    raw_plugins = data.get("plugins") or data.get("providers") or []
    if raw_plugins is None:
        raw_plugins = []
    if isinstance(raw_plugins, dict):
        raw_plugins = [{"provider_id": k, **(v or {})} for k, v in raw_plugins.items()]
    if not isinstance(raw_plugins, list):
        raise ConfigError("Campo plugins/providers deve ser lista ou mapa.", details={"type": str(type(raw_plugins))})

    specs: list[PluginSpec] = []
    for item in raw_plugins:
        if not isinstance(item, dict):
            continue
        provider_id = str(item.get("provider_id") or item.get("id") or "").strip()
        import_path = str(item.get("import_path") or item.get("adapter") or "").strip()
        if provider_id and import_path:
            specs.append(PluginSpec(provider_id=provider_id, import_path=import_path))
    return specs
