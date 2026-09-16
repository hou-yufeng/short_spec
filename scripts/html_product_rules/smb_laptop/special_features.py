from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Callable, Iterable


SPECIAL_FEATURES_KEY = "special features"
_REMOVED_MARKS = {"\u00ae", "\u2122", "\u00a9", "\u2120", "\u5e90", "\u9229", "\u2499", "\ue7e4", "\ufffd"}
_ALLOWED_SYMBOLS = {"+", "#"}


def _label_key(value: str) -> str:
    value = html.unescape(str(value))
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = re.sub(r"\*+$", "", value)
    value = re.sub(r"[^a-z0-9+&/(). -]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip(" :")


def sanitize_special_feature_value(value: str) -> str:
    value = html.unescape(str(value)).replace("\u00a0", " ")
    cleaned: list[str] = []
    for character in value:
        if character in _REMOVED_MARKS:
            continue
        category = unicodedata.category(character)
        if category.startswith("C"):
            continue
        if category.startswith("S") and character not in _ALLOWED_SYMBOLS:
            continue
        cleaned.append(character)
    return re.sub(r"\s+", " ", "".join(cleaned)).strip()


def normalize_special_feature_values(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        key = _label_key(str(value))
        if key == SPECIAL_FEATURES_KEY:
            continue
        if key in {"notes", "notes:"} or re.fullmatch(r"\[[0-9,\s]+\].*", str(value).strip()):
            break
        cleaned = sanitize_special_feature_value(str(value))
        if cleaned:
            output.append(cleaned)
    return output


def extract_special_features_from_lines(
    lines: list[str],
    label_key: Callable[[str], str],
    is_stop_line: Callable[[str], bool],
) -> list[str]:
    start: int | None = None
    for index, line in enumerate(lines):
        if label_key(line) == SPECIAL_FEATURES_KEY:
            start = index
            break
    if start is None:
        return []

    values: list[str] = []
    for line in lines[start + 1 :]:
        if label_key(line) == SPECIAL_FEATURES_KEY:
            continue
        if is_stop_line(line):
            break
        values.append(line)
    return normalize_special_feature_values(values)
