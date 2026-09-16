from __future__ import annotations

import html
import re
from collections.abc import Iterable


KEYBOARD_LABELS = ["Keyboard", "Keyboard**"]
KEYBOARD_BACKLIGHT_LABELS = ["Keyboard Backlight", "Keyboard Backlight**"]
KEYBOARD_STOP_LABELS = [
    "Keyboard Backlight",
    "UltraNav",
    "Touchpad",
    "Mouse",
    "Mechanical",
    "Form Factor",
    "Dimensions (WxDxH)",
    "Weight",
    "CONNECTIVITY",
    "Notes",
    "Notes:",
]
KEYBOARD_BACKLIGHT_STOP_LABELS = [
    "UltraNav",
    "Touchpad",
    "Mouse",
    "Mechanical",
    "Form Factor",
    "Dimensions (WxDxH)",
    "Weight",
    "CONNECTIVITY",
    "Notes",
    "Notes:",
]


def label_key(value: str) -> str:
    value = html.unescape(str(value)).replace("\u00a0", " ")
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = re.sub(r"\*+$", "", value)
    value = re.sub(r"[^a-z0-9+&/(). -]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip(" :")


def normalize_value(value: str) -> str:
    value = html.unescape(str(value)).replace("\u00a0", " ")
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.strip(" ,;")


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = normalize_value(value)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def find_label_index(lines: list[str], labels: Iterable[str]) -> int | None:
    wanted = {label_key(label) for label in labels}
    for index, line in enumerate(lines):
        if label_key(line) in wanted:
            return index
    return None


def slice_after_label(lines: list[str], labels: Iterable[str], stop_labels: Iterable[str]) -> list[str]:
    start = find_label_index(lines, labels)
    if start is None:
        return []

    stops = {label_key(label) for label in stop_labels}
    captured: list[str] = []
    for line in lines[start + 1 :]:
        key = label_key(line)
        if key in stops or key.startswith("notes"):
            break
        captured.append(line)
    return unique_preserve(captured)


def strip_condition_prefix(value: str) -> str:
    value = normalize_value(value)
    if ":" not in value:
        return value
    prefix, suffix = value.split(":", 1)
    if suffix.strip() and len(prefix.strip()) <= 80:
        return normalize_value(suffix)
    return value


def is_none_or_no_value(value: str) -> bool:
    lowered = normalize_value(value).lower()
    return "none" in lowered or lowered.startswith("no")


def is_ignored_option(value: str) -> bool:
    return is_none_or_no_value(strip_condition_prefix(value))


def summarize_keyboard_backlight_values(values: Iterable[str]) -> str:
    raw_values = unique_preserve(values)
    positive_values = [strip_condition_prefix(value) for value in raw_values if not is_ignored_option(value)]
    positive_values = unique_preserve(positive_values)
    if not positive_values:
        return ""
    return " / ".join(positive_values)


def keyboard_tokens_from_value(value: str) -> list[tuple[int, str]]:
    lowered = value.lower()
    tokens: list[tuple[int, str]] = []

    row_match = re.search(r"\b\d+-row\b", value, flags=re.I)
    if row_match:
        tokens.append((row_match.start(), row_match.group(0)))

    for needle, rendered in [
        ("multimedia fn keys", "multimedia Fn keys"),
        ("spill-resistant", "spill-resistant"),
        ("chrome keyboard", "Chrome keyboard"),
    ]:
        index = lowered.find(needle)
        if index >= 0:
            tokens.append((index, rendered))

    return sorted(tokens, key=lambda item: item[0])


def summarize_mobile_keyboard_values(keyboard_values: Iterable[str]) -> str:
    values = [value for value in unique_preserve(keyboard_values) if not is_ignored_option(value)]
    extracted: list[str] = []
    seen: set[str] = set()

    for value in values:
        for _, token in keyboard_tokens_from_value(value):
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            extracted.append(token)

    if extracted:
        return ", ".join(extracted)
    return "\n".join(values)


def combine_keyboard_and_backlight(keyboard_text: str, backlight_text: str) -> list[str]:
    parts = [part for part in [keyboard_text.strip(), backlight_text.strip()] if part]
    if not parts:
        return []
    return ["\n".join(parts)]


def summarize_mobile_keyboard(keyboard_values: Iterable[str], backlight_values: Iterable[str]) -> list[str]:
    return combine_keyboard_and_backlight(
        summarize_mobile_keyboard_values(keyboard_values),
        summarize_keyboard_backlight_values(backlight_values),
    )


def summarize_mobile_keyboard_from_lines(lines: list[str]) -> list[str]:
    return summarize_mobile_keyboard(
        slice_after_label(lines, KEYBOARD_LABELS, KEYBOARD_STOP_LABELS),
        slice_after_label(lines, KEYBOARD_BACKLIGHT_LABELS, KEYBOARD_BACKLIGHT_STOP_LABELS),
    )


def summarize_desktop_keyboard_values(keyboard_values: Iterable[str]) -> str:
    values = [
        strip_condition_prefix(value)
        for value in unique_preserve(keyboard_values)
        if not is_ignored_option(value)
    ]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return "\n".join(f"- {value}" for value in values)


def summarize_desktop_keyboard(keyboard_values: Iterable[str], backlight_values: Iterable[str]) -> list[str]:
    return combine_keyboard_and_backlight(
        summarize_desktop_keyboard_values(keyboard_values),
        summarize_keyboard_backlight_values(backlight_values),
    )


def summarize_desktop_keyboard_from_lines(lines: list[str]) -> list[str]:
    return summarize_desktop_keyboard(
        slice_after_label(lines, KEYBOARD_LABELS, KEYBOARD_STOP_LABELS),
        slice_after_label(lines, KEYBOARD_BACKLIGHT_LABELS, KEYBOARD_BACKLIGHT_STOP_LABELS),
    )
