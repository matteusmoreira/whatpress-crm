from __future__ import annotations

import logging
import os
from functools import lru_cache

from .config import load_whatsapp_config
from .connection_manager import ConnectionManager
from .observability import Observability
from .providers.evolution import EvolutionWhatsAppProvider
from .providers.registry import ProviderRegistry
from .providers.stub import StubWhatsAppProvider
from .providers.uazapi import UazapiWhatsAppProvider


@lru_cache(maxsize=1)
def get_whatsapp_container() -> "WhatsAppContainer":
    return WhatsAppContainer.build()


class WhatsAppContainer:
    def __init__(self, *, registry: ProviderRegistry, obs: Observability, connections: ConnectionManager):
        self.registry = registry
        self.obs = obs
        self.connections = connections

    @staticmethod
    def build() -> "WhatsAppContainer":
        logger = logging.getLogger("whatsapp")
        obs = Observability(logger)
        registry = ProviderRegistry()
        connections = ConnectionManager(obs=obs)

        default_evolution_base_url = (
            (os.getenv("EVOLUTION_API_BASE_URL") or "").strip()
            or (os.getenv("EVOLUTION_BASE_URL") or "").strip()
            or (os.getenv("EVOLUTION_URL") or "").strip()
        )
        default_evolution_api_key = (
            (os.getenv("EVOLUTION_API_KEY") or "").strip()
            or (os.getenv("EVOLUTION_KEY") or "").strip()
            or (os.getenv("EVOLUTION_API_TOKEN") or "").strip()
        )
        default_uazapi_base_url = (os.getenv("UAZAPI_BASE_URL") or "").strip()
        default_uazapi_admin_token = (os.getenv("UAZAPI_ADMIN_TOKEN") or "").strip()
        registry.register(
            EvolutionWhatsAppProvider(
                default_base_url=default_evolution_base_url,
                default_api_key=default_evolution_api_key,
            )
        )
        registry.register(
            UazapiWhatsAppProvider(
                default_base_url=default_uazapi_base_url,
                default_admin_token=default_uazapi_admin_token,
            )
        )
        registry.register(StubWhatsAppProvider("wuzapi"))
        registry.register(StubWhatsAppProvider("pastorini"))

        cfg = load_whatsapp_config()
        if cfg.plugins:
            registry.load_plugins(cfg.plugins)

        return WhatsAppContainer(registry=registry, obs=obs, connections=connections)
