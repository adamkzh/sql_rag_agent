import re
from typing import Any, Dict, List

PII_FIELDS = {"email", "phone", "address"}


def mask_email(value: str) -> str:
    if "@" not in value:
        return "[REDACTED]"
    name, domain = value.split("@", 1)
    if not name:
        return "[REDACTED]"
    return f"{name[0]}***@{domain}"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\\D", "", value)
    if len(digits) < 4:
        return "***"
    return f"***-***-{digits[-4:]}"


def mask_address(_: str) -> str:
    return "[REDACTED]"


MASKERS = {
    "email": mask_email,
    "phone": mask_phone,
    "address": mask_address,
}


def mask_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Mask known PII fields in a row dict."""
    masked = dict(record)
    for field, masker in MASKERS.items():
        if field in masked and masked[field] is not None:
            masked[field] = masker(str(masked[field]))
    return masked


def contains_pii_fields(columns: List[str]) -> bool:
    return any(col.lower() in PII_FIELDS for col in columns)
