# This file contains small helper functions used by the rest of Synapse.
from __future__ import annotations

import re
import textwrap


def compact(text: str, limit: int = 700) -> str:
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def dedent(text: str) -> str:
    return textwrap.dedent(text).strip()


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def parse_labeled_field(text: str, label: str) -> str:
    labels = [
        "Main weakness",
        "MAIN_WEAKNESS",
        "Risk",
        "RISK",
        "Missing element",
        "MISSING_ELEMENT",
        "Unclear assumption",
        "UNCLEAR_ASSUMPTION",
        "Suggested improvement",
        "SUGGESTED_IMPROVEMENT",
    ]
    label_pattern = "|".join(re.escape(item) for item in labels)
    pattern = (
        rf"(?:^|\n)\s*(?:#+\s*)?(?:[-*]\s*)?"
        rf"(?:\*\*)?\s*{re.escape(label)}\s*(?:\*\*)?\s*:\s*"
        rf"(.*?)(?=\n\s*(?:#+\s*)?(?:[-*]\s*)?(?:\*\*)?\s*(?:{label_pattern})\s*(?:\*\*)?\s*:|\Z)"
    )
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return clean_markdown_label(match.group(1))


def raw_fallback_summary(text: str, limit: int = 260) -> str:
    return compact(text, limit) if text.strip() else "Raw critique was empty."


def clean_markdown_label(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\*+\s*", "", cleaned)
    cleaned = re.sub(r"\s*\*+$", "", cleaned)
    return cleaned.strip()


def first_nonempty(*values: str, fallback: str = "Not provided.") -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return fallback


def strip_response_label(text: str, labels: list[str]) -> str:
    cleaned = text.strip()
    for label in labels:
        pattern = rf"^\s*(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*:\s*"
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()
