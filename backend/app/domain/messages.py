"""Structured reason/warning codes shared by domain calculation modules.

A Message carries a stable, machine-readable `code` plus structured
`params` so a frontend can translate it into Uzbek (see
frontend/src/utils/labels.ts and frontend/src/i18n/uz.json) instead of
pattern-matching English prose or showing raw internal strings/keys
directly. `text_en` is the original human-readable English sentence, kept
only for the technical/expert debug section — never the primary
farmer-facing content (see CLAUDE.md and docs/methodology.md).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Message:
    code: str
    text_en: str
    params: dict[str, Any] = field(default_factory=dict)
