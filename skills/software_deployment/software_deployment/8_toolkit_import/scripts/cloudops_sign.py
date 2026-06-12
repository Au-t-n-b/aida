from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Any

try:
    from requests_toolbelt import MultipartEncoder
except ImportError:  # pragma: no cover
    MultipartEncoder = None  # type: ignore[misc, assignment]


def convert_ipv4_to_ak(ipv4: str) -> str:
    """与 workbench / legacy rest_utils 对齐的 IPv4 → AccessKey。"""
    text = str(ipv4 or "").strip()
    if not text:
        return ""
    parts = text.split(".")
    if len(parts) != 4:
        raise ValueError("Invalid IPv4 address format")
    ip_bytes: list[int] = []
    for part in parts:
        num = int(part)
        if not (0 <= num <= 255):
            raise ValueError(f"IPv4 part out of range: {part}")
        ip_bytes.append(num)
    return f"AK_{hashlib.sha256(bytes(ip_bytes)).hexdigest()}"


def build_canonical_headers(headers: Mapping[str, Any], key_list: str) -> str:
    values: list[str] = []
    for key in key_list.split(";"):
        values.append(f"{key}:{headers.get(key, '')}")
    return "\n".join(values)


def _hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_mapping_body(data: Mapping[str, Any]) -> str:
    body = json.dumps(data, ensure_ascii=False).replace(" ", "")
    return _hash_bytes(body.encode("utf-8"))


def _hash_multipart_like_body(data: Mapping[str, Any]) -> str:
    chunks: list[bytes] = []
    for key, value in data.items():
        if key == "file":
            if isinstance(value, (tuple, list)) and len(value) > 1:
                file_bytes = value[1]
            else:
                file_bytes = value
            if isinstance(file_bytes, str):
                raw = file_bytes.encode("utf-8")
            elif isinstance(file_bytes, bytes):
                raw = file_bytes
            else:
                raw = bytes(file_bytes)
            chunks.append(b"file:" + raw)
            continue
        if isinstance(value, (tuple, list)) and len(value) > 1:
            field_value = value[1]
        else:
            field_value = value
        chunks.append(f"{key}:{field_value}".encode("utf-8"))
    return _hash_bytes(b",".join(chunks))


def _hash_multipart_encoder_body(encoder: Any) -> str:
    fields = encoder.fields
    chunks: list[bytes] = []
    for field_key in fields.keys():
        if field_key == "file":
            file_content_bytes = fields["file"][1]
            chunks.append(b"file:" + file_content_bytes)
            continue
        fields_value = fields[field_key]
        if isinstance(fields_value, (list, tuple)) and len(fields_value) > 1:
            chunks.append(f"{field_key}:{fields_value[1]}".encode("utf-8"))
        else:
            chunks.append(f"{field_key}:{fields[field_key]}".encode("utf-8"))
    return _hash_bytes(b",".join(chunks))


def build_hash_payload(request_body: Any) -> str:
    if request_body is None:
        return ""
    if MultipartEncoder is not None and isinstance(request_body, MultipartEncoder):
        return _hash_multipart_encoder_body(request_body)
    if isinstance(request_body, bytes):
        return _hash_bytes(request_body)
    if isinstance(request_body, str):
        return _hash_bytes(request_body.encode("utf-8"))
    if isinstance(request_body, Mapping):
        if "file" in request_body:
            return _hash_multipart_like_body(request_body)
        return _hash_mapping_body(request_body)
    return _hash_bytes(str(request_body).encode("utf-8"))


def generate_signature_hmac_sha256(
    secret_key: str,
    method: str,
    url: str,
    canonical_query_string: str,
    canonical_headers: str,
    headers_to_be_signed: str,
    body: Any,
) -> str:
    hashed_payload = build_hash_payload(body)
    signature_text = "\n".join(
        [
            method.upper(),
            url.replace("/", "%2F"),
            str(canonical_query_string or "").lower(),
            canonical_headers.lower(),
            headers_to_be_signed.lower(),
            hashed_payload,
        ]
    )
    return hmac.new(
        secret_key.encode("utf-8"),
        signature_text.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
