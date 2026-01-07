from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DetectedMedia:
    kind: str
    mime_type: str
    confidence: str


_EXT_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".3gp": "video/3gpp",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
}


def _safe_lower(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _guess_mime_from_extension(filename: Optional[str]) -> str:
    if not filename:
        return ""
    name = filename.strip().lower()
    dot = name.rfind(".")
    if dot < 0:
        return ""
    ext = name[dot:]
    return _EXT_TO_MIME.get(ext, "")


def _sniff_mime_from_bytes(head: bytes) -> str:
    if not head:
        return ""

    if head.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"ID3"):
        return "audio/mpeg"
    if len(head) >= 12 and head[0:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if len(head) >= 12 and head[0:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/mp4"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"

    return ""


def _kind_from_mime(mime_type: str) -> str:
    mt = _safe_lower(mime_type)
    if not mt:
        return "unknown"
    if mt == "image/webp":
        return "sticker"
    if mt.startswith("image/"):
        return "image"
    if mt.startswith("audio/") or "opus" in mt or mt.endswith("+opus"):
        return "audio"
    if mt.startswith("video/"):
        return "video"
    return "document"


def detect_media_kind(
    *,
    declared_mime_type: Optional[str] = None,
    filename: Optional[str] = None,
    head_bytes: Optional[bytes] = None,
    hinted_kind: Optional[str] = None,
) -> DetectedMedia:
    hinted = _safe_lower(hinted_kind)
    if hinted in {"image", "audio", "video", "document", "sticker"}:
        mime = _safe_lower(declared_mime_type) or _guess_mime_from_extension(filename) or _sniff_mime_from_bytes(head_bytes or b"") or "application/octet-stream"
        if hinted == "sticker" and mime != "image/webp":
            mime = "image/webp"
        return DetectedMedia(kind=hinted, mime_type=mime, confidence="high")

    sniffed = _sniff_mime_from_bytes(head_bytes or b"")
    if sniffed:
        return DetectedMedia(kind=_kind_from_mime(sniffed), mime_type=sniffed, confidence="high")

    declared = _safe_lower(declared_mime_type)
    ext_mime = _guess_mime_from_extension(filename)

    if declared:
        kind = _kind_from_mime(declared)
        return DetectedMedia(kind=kind, mime_type=declared, confidence="medium")

    if ext_mime:
        kind = _kind_from_mime(ext_mime)
        return DetectedMedia(kind=kind, mime_type=ext_mime, confidence="low")

    return DetectedMedia(kind="unknown", mime_type="application/octet-stream", confidence="low")

