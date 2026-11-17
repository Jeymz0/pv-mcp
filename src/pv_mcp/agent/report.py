"""Write the approved Markdown summary."""

import re
from datetime import UTC, datetime
from pathlib import Path

from pv_mcp.openfda.models import DISCLAIMER

_SLUG = re.compile(r"[^a-z0-9]+")


def ensure_disclaimer(body: str) -> str:
    """Keep the approved file from leaving without the standard limit."""

    text = body.strip()
    if DISCLAIMER in text:
        return text + "\n"
    return f"{text}\n\n{DISCLAIMER}\n"


def write_report(directory: Path, *, drug: str, body: str, now: datetime) -> Path:
    """Save one approved summary. The file name carries the drug and the time."""

    directory.mkdir(parents=True, exist_ok=True)
    slug = _SLUG.sub("-", drug.lower()).strip("-") or "drug"
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{slug}-{stamp}.md"
    path.write_text(ensure_disclaimer(body), encoding="utf-8")
    return path
