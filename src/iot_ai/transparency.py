# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Article 50 interaction disclosure and machine-readable provenance marks."""
from __future__ import annotations

import binascii
import json
import re
import struct
import zlib
from pathlib import Path
from typing import Any

from .eu_ai_act import _append_jsonl
from .paths import disclosure_receipts_path
from .privacy import sanitize
from .suite_version import SUITE_VERSION
from .util import atomic_bytes, atomic_json, atomic_text, sha256_bytes, sha256_file, utc_now

DISCLOSURES: dict[str, dict[str, str]] = {
    "en": {
        "title": "AI interaction notice",
        "text": (
            "You are interacting with an AI system operated by IoT-AI.Tech. "
            "Outputs may be inaccurate or incomplete. Material actions require human approval, "
            "and provider/model details are available in the session evidence."
        ),
    },
    "de": {
        "title": "Hinweis zur KI-Interaktion",
        "text": (
            "Sie interagieren mit einem von IoT-AI.Tech betriebenen KI-System. "
            "Ausgaben können unzutreffend oder unvollständig sein. Wesentliche Aktionen erfordern "
            "eine menschliche Freigabe; Anbieter- und Modellangaben stehen in den Sitzungsnachweisen."
        ),
    },
    "fa": {
        "title": "اعلان تعامل با هوش مصنوعی",
        "text": (
            "شما با یک سامانه هوش مصنوعی تحت مسئولیت IoT-AI.Tech تعامل می‌کنید. "
            "خروجی‌ها ممکن است نادرست یا ناقص باشند. اقدامات مهم نیازمند تأیید انسانی هستند و "
            "اطلاعات ارائه‌دهنده و مدل در شواهد نشست ثبت می‌شود."
        ),
    },
}

VISIBLE_LABELS = {
    "en": "AI-assisted content. Human review and editorial responsibility must be recorded before publication.",
    "de": "KI-unterstützter Inhalt. Vor der Veröffentlichung müssen menschliche Prüfung und redaktionelle Verantwortung dokumentiert sein.",
    "fa": "محتوای تولیدشده با کمک هوش مصنوعی؛ پیش از انتشار باید بازبینی انسانی و مسئولیت تحریریه ثبت شود.",
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_KEYWORD = b"IOT-AI-Provenance"


def disclosure_payload(*, surface: str, language: str = "en", provider: str = "IoT-AI.Tech") -> dict[str, Any]:
    normalized = language.casefold()
    if normalized not in DISCLOSURES:
        normalized = "en"
    value = DISCLOSURES[normalized]
    return {
        "schema": "iot-ai.article-50-interaction-disclosure.v1",
        "ai_interaction": True,
        "operator": provider,
        "system": "IOT-AI Suite",
        "system_version": SUITE_VERSION,
        "surface": surface,
        "language": normalized,
        "title": value["title"],
        "text": value["text"],
        "disclosure_version": "1.0.0",
        "human_approval_required_for_material_actions": True,
        "shown_at": utc_now(),
        "accessibility": {"plain_text": True, "screen_reader_compatible": True},
    }


def record_disclosure(user_home: Path, *, surface: str, language: str = "en") -> dict[str, Any]:
    """Record a privacy-minimised first-interaction disclosure receipt."""
    payload = disclosure_payload(surface=surface, language=language)
    receipt = {
        "schema": "iot-ai.article-50-disclosure-receipt.v1",
        "receipt_id": "a50-" + sha256_bytes(f"{surface}:{payload['shown_at']}".encode("utf-8"))[:20],
        "surface": surface,
        "language": payload["language"],
        "system_version": SUITE_VERSION,
        "disclosure_version": payload["disclosure_version"],
        "shown_at": payload["shown_at"],
        "text_sha256": sha256_bytes(payload["text"].encode("utf-8")),
        "personal_identity_stored": False,
    }
    _append_jsonl(disclosure_receipts_path(user_home), receipt)
    return {"disclosure": payload, "receipt": receipt}


def visible_label(*, language: str = "en", reviewed_by: str | None = None) -> str:
    normalized = language.casefold() if language.casefold() in VISIBLE_LABELS else "en"
    base = VISIBLE_LABELS[normalized]
    if reviewed_by:
        safe = sanitize(reviewed_by, "strict")
        if safe.decision == "block":
            raise ValueError("reviewer label contains secret-like material")
        return f"{base} Reviewed by: {safe.text}."
    return base


def provenance_payload(
    *,
    content_sha256: str,
    content_type: str,
    system_id: str = "iot-ai-tech.iot-ai-coder-suite",
    model_providers: list[str] | None = None,
    model_ids: list[str] | None = None,
    ai_generated: bool = True,
    ai_assisted: bool = True,
    human_reviewed: bool = False,
    editorially_responsible_party: str | None = None,
    public_interest: bool = False,
    deepfake: bool = False,
    visible_label_present: bool = False,
) -> dict[str, Any]:
    if public_interest and not (human_reviewed and editorially_responsible_party) and not visible_label_present:
        raise ValueError("public-interest content requires substantive human editorial control or a visible AI label")
    if deepfake and not visible_label_present:
        raise ValueError("deepfake content requires a visible human-readable label")
    return {
        "schema": "iot-ai.ai-content-provenance.v1",
        "content_sha256": content_sha256,
        "content_type": content_type,
        "ai_generated": ai_generated,
        "ai_assisted": ai_assisted,
        "human_reviewed": human_reviewed,
        "editorially_responsible_party": editorially_responsible_party,
        "generator_system": system_id,
        "generator_version": SUITE_VERSION,
        "model_providers": sorted(set(model_providers or [])),
        "model_ids": sorted(set(model_ids or [])),
        "generated_at": utc_now(),
        "public_interest": public_interest,
        "deepfake": deepfake,
        "visible_label_present": visible_label_present,
        "transparency_profile": "eu-ai-act-article-50-v1",
        "claim": "provenance-receipt-not-authenticity-or-legal-certification",
    }


def runtime_output_provenance(
    content: str | bytes,
    *,
    content_type: str = "text/plain",
    model_providers: list[str] | None = None,
    model_ids: list[str] | None = None,
    human_reviewed: bool = False,
    editorially_responsible_party: str | None = None,
) -> dict[str, Any]:
    """Return an inline machine-readable provenance mark for runtime output.

    The digest is bound to the generated content body, not to the surrounding
    transport envelope, so the mark can be preserved in JSON, API and CLI
    payloads without a self-referential hash.  This is a technical mark and
    never a legal certification or authenticity guarantee.
    """
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    return provenance_payload(
        content_sha256=sha256_bytes(raw),
        content_type=content_type,
        model_providers=model_providers,
        model_ids=model_ids,
        human_reviewed=human_reviewed,
        editorially_responsible_party=editorially_responsible_party,
    )


def _sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + ".ai-provenance.json")


def _strip_markdown_mark(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    front = [line for line in text[4:end].splitlines() if not line.startswith("iot_ai_provenance: ")]
    body = text[end + 5 :]
    return "---\n" + "\n".join(front) + ("\n" if front else "") + "---\n" + body


def _strip_html_mark(text: str) -> str:
    text = re.sub(r'\s*<meta name="iot-ai-generated"[^>]*>\s*', "\n", text, flags=re.I)
    text = re.sub(r'\s*<meta name="iot-ai-transparency-profile"[^>]*>\s*', "\n", text, flags=re.I)
    text = re.sub(
        r'\s*<script type="application/ld\+json" id="iot-ai-provenance">.*?</script>\s*',
        "\n",
        text,
        flags=re.I | re.S,
    )
    return text


def _strip_text_mark(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    prefixes = tuple(VISIBLE_LABELS.values()) + ("IOT-AI-PROVENANCE: ",)
    while lines and (not lines[0].strip() or any(lines[0].startswith(prefix) for prefix in prefixes)):
        lines.pop(0)
    return "\n".join(lines) + ("\n" if text.endswith("\n") and lines else "")


def _strip_png_mark(data: bytes) -> bytes:
    output = bytearray(PNG_SIGNATURE)
    for ctype, value in _png_chunks(data):
        if ctype in {b"tEXt", b"zTXt", b"iTXt"} and value.startswith(PNG_KEYWORD + b"\x00"):
            continue
        output.extend(_chunk(ctype, value))
    return bytes(output)


def _mark_markdown(text: str, payload: dict[str, Any]) -> str:
    text = _strip_markdown_mark(text)
    marker = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    line = f"iot_ai_provenance: {marker}\n"
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[: end + 1] + line + text[end + 1 :]
    return f"---\n{line}---\n\n{text}"


def _mark_html(text: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    metadata = (
        '<meta name="iot-ai-generated" content="true">\n'
        '<meta name="iot-ai-transparency-profile" content="eu-ai-act-article-50-v1">\n'
        f'<script type="application/ld+json" id="iot-ai-provenance">{canonical}</script>\n'
    )
    lower = text.casefold()
    index = lower.find("</head>")
    if index >= 0:
        return text[:index] + metadata + text[index:]
    return metadata + text


def _png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")
    chunks: list[tuple[bytes, bytes]] = []
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        ctype = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        crc = data[offset + 8 + length : offset + 12 + length]
        expected = binascii.crc32(ctype + payload) & 0xFFFFFFFF
        if len(crc) != 4 or struct.unpack(">I", crc)[0] != expected:
            raise ValueError("invalid PNG CRC")
        chunks.append((ctype, payload))
        offset += 12 + length
        if ctype == b"IEND":
            break
    return chunks


def _chunk(ctype: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + ctype + payload + struct.pack(">I", binascii.crc32(ctype + payload) & 0xFFFFFFFF)


def _mark_png(data: bytes, payload: dict[str, Any]) -> bytes:
    chunks = _png_chunks(data)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = PNG_KEYWORD + b"\x00\x00" + zlib.compress(canonical, 9)
    output = bytearray(PNG_SIGNATURE)
    inserted = False
    for ctype, value in chunks:
        if ctype in {b"tEXt", b"zTXt", b"iTXt"} and value.startswith(PNG_KEYWORD + b"\x00"):
            continue
        output.extend(_chunk(ctype, value))
        if ctype == b"IHDR" and not inserted:
            output.extend(_chunk(b"zTXt", compressed))
            inserted = True
    return bytes(output)


def _read_png_provenance(data: bytes) -> dict[str, Any] | None:
    for ctype, value in _png_chunks(data):
        if ctype == b"zTXt" and value.startswith(PNG_KEYWORD + b"\x00\x00"):
            raw = zlib.decompress(value[len(PNG_KEYWORD) + 2 :])
            return json.loads(raw.decode("utf-8"))
    return None


def mark_file(
    path: Path,
    *,
    model_providers: list[str] | None = None,
    model_ids: list[str] | None = None,
    human_reviewed: bool = False,
    editorially_responsible_party: str | None = None,
    public_interest: bool = False,
    deepfake: bool = False,
    visible_label_present: bool = False,
) -> dict[str, Any]:
    """Embed or sidecar an Article 50 provenance record.

    Markdown, HTML, JSON, PNG and plain text receive embedded structured
    metadata. CSV and other media receive a hash-bound sidecar and remain
    ``needs-work`` until an interoperable mark appropriate to that format is
    applied. Existing IOT-AI marks are removed before recalculation so repeated
    marking never accumulates stale metadata.
    """
    path = path.expanduser().resolve()
    if not path.is_file() or path.is_symlink():
        raise ValueError("mark target must be a regular file")
    suffix = path.suffix.casefold()
    original = path.read_bytes()
    content_type = suffix.lstrip(".") or "binary"

    clean = original
    if suffix in {".md", ".markdown"}:
        clean = _strip_markdown_mark(original.decode("utf-8")).encode("utf-8")
    elif suffix in {".html", ".htm"}:
        clean = _strip_html_mark(original.decode("utf-8")).encode("utf-8")
    elif suffix == ".json":
        value = json.loads(original.decode("utf-8"))
        if isinstance(value, dict):
            value = dict(value)
            value.pop("_iot_ai_provenance", None)
        clean = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    elif suffix == ".png":
        clean = _strip_png_mark(original)
    elif suffix == ".txt":
        clean = _strip_text_mark(original.decode("utf-8")).encode("utf-8")

    initial_hash = sha256_bytes(clean)
    base_payload = provenance_payload(
        content_sha256=initial_hash,
        content_type=content_type,
        model_providers=model_providers,
        model_ids=model_ids,
        human_reviewed=human_reviewed,
        editorially_responsible_party=editorially_responsible_party,
        public_interest=public_interest,
        deepfake=deepfake,
        visible_label_present=visible_label_present,
    )
    embedded = False
    if suffix in {".md", ".markdown"}:
        atomic_text(path, _mark_markdown(clean.decode("utf-8"), base_payload), mode=0o644)
        embedded = True
    elif suffix in {".html", ".htm"}:
        atomic_text(path, _mark_html(clean.decode("utf-8"), base_payload), mode=0o644)
        embedded = True
    elif suffix == ".json":
        value = json.loads(clean.decode("utf-8"))
        if isinstance(value, dict):
            value["_iot_ai_provenance"] = base_payload
        else:
            value = {"_iot_ai_provenance": base_payload, "content": value}
        atomic_json(path, value, mode=0o644)
        embedded = True
    elif suffix == ".png":
        atomic_bytes(path, _mark_png(clean, base_payload), mode=0o644)
        embedded = True
    elif suffix == ".txt":
        canonical = json.dumps(base_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        label = visible_label(language="en", reviewed_by=editorially_responsible_party if human_reviewed else None)
        atomic_text(path, f"IOT-AI-PROVENANCE: {canonical}\n{label}\n\n{clean.decode('utf-8')}", mode=0o644)
        embedded = True

    final_hash = sha256_file(path)
    receipt = {
        **base_payload,
        "source_content_sha256": initial_hash,
        "marked_content_sha256": final_hash,
        "file_name": path.name,
        "embedded": embedded,
        "external_interoperable_mark_required": not embedded,
    }
    sidecar = _sidecar_path(path)
    atomic_json(sidecar, receipt, mode=0o644)
    return {
        "decision": "pass" if embedded else "needs-work",
        "file": str(path),
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256_file(sidecar),
        "receipt": receipt,
    }

def verify_file(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    sidecar = _sidecar_path(path)
    if not path.is_file() or not sidecar.is_file():
        return {"decision": "block", "errors": ["file-or-sidecar-missing"]}
    receipt = json.loads(sidecar.read_text(encoding="utf-8"))
    current = sha256_file(path)
    errors: list[str] = []
    if receipt.get("marked_content_sha256") != current:
        errors.append("marked-content-hash-mismatch")
    embedded: dict[str, Any] | None = None
    suffix = path.suffix.casefold()
    if suffix == ".png":
        embedded = _read_png_provenance(path.read_bytes())
    elif suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        embedded = value.get("_iot_ai_provenance") if isinstance(value, dict) else None
    elif suffix in {".md", ".markdown"}:
        first = path.read_text(encoding="utf-8").splitlines()[:8]
        marker = next((line.split(": ", 1)[1] for line in first if line.startswith("iot_ai_provenance: ")), None)
        embedded = json.loads(marker) if marker else None
    elif suffix in {".html", ".htm"}:
        text = path.read_text(encoding="utf-8")
        start = text.find('<script type="application/ld+json" id="iot-ai-provenance">')
        if start >= 0:
            start = text.find(">", start) + 1
            end = text.find("</script>", start)
            embedded = json.loads(text[start:end].replace("<\\/", "</"))
    elif suffix == ".txt":
        first = path.read_text(encoding="utf-8").splitlines()[:2]
        marker = next((line.split(": ", 1)[1] for line in first if line.startswith("IOT-AI-PROVENANCE: ")), None)
        embedded = json.loads(marker) if marker else None
    if receipt.get("embedded") and embedded is None:
        errors.append("embedded-mark-missing")
    if embedded:
        embedded_source = embedded.get("source_content_sha256") or embedded.get("content_sha256")
        if embedded_source != receipt.get("source_content_sha256"):
            errors.append("embedded-sidecar-source-mismatch")
    return {
        "schema": "iot-ai.ai-content-provenance-verification.v1",
        "decision": "pass" if not errors else "block",
        "errors": errors,
        "file_sha256": current,
        "sidecar_sha256": sha256_file(sidecar),
        "embedded": embedded is not None,
        "transparency_profile": receipt.get("transparency_profile"),
    }
