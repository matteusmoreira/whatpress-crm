"""Funções utilitárias para o provider UAZAPI."""
from __future__ import annotations

import re
from typing import Any, Optional


def format_phone(phone: str) -> str:
    """Formata número de telefone para padrão brasileiro."""
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10:
        return f"55{digits}"
    if len(digits) == 11 and not digits.startswith("55"):
        return f"55{digits}"
    return digits


def map_kind_to_media_type(kind: str) -> Optional[str]:
    """Mapeia tipo de mídia para valores aceitos pela API v2.
    
    Tipos suportados: image, video, audio, document, ptt, ptv, sticker, myaudio
    """
    mapping = {
        "image": "image", "photo": "image", "picture": "image",
        "video": "video",
        "audio": "audio", "voice": "audio",
        "ptt": "ptt", "voice_message": "ptt",
        "document": "document", "file": "document", "pdf": "document",
        "sticker": "sticker",
    }
    return mapping.get((kind or "").strip().lower())


def extract_qrcode(obj: Any) -> Optional[str]:
    """Extrai valor do QR code de várias estruturas de resposta."""
    if not isinstance(obj, dict):
        return None
    
    def pick(d: dict[str, Any]) -> Optional[str]:
        if isinstance(d.get("base64"), str) and d["base64"].strip():
            return d["base64"].strip()
        for k in ("qrcode", "qr", "qrCode", "qr_code"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                nested = v.get("base64") or v.get("qrcode") or v.get("qr")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
        return None
    
    direct = pick(obj)
    if direct:
        return direct
    
    for k in ("instance", "data", "response"):
        nested = obj.get(k)
        if isinstance(nested, dict):
            val = pick(nested)
            if val:
                return val
    return None


def normalize_base_url(base_url: str) -> str:
    """Normaliza URL base removendo sufixos de versão e paths."""
    raw = str(base_url or "").strip()
    if not raw:
        return ""
    
    b = raw.rstrip("/")
    lowered = b.lower()
    for marker in ("/instance", "/message", "/send", "/webhook", "/group", "/chat"):
        if lowered.endswith(marker):
            b = b[: -len(marker)]
            break
    
    return b.rstrip("/")
