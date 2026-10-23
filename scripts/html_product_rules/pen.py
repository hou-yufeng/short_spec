"""Pen ShortSpec rules shared by the product lines that generate Pen."""

from __future__ import annotations

import re


def _starts_with_uppercase_or_digit(word: str) -> bool:
    word = word.lstrip("([{\"'")
    return bool(word) and (word[0].isupper() or word[0].isdigit())


def _pen_phrase(value: str) -> str:
    pen_at = value.find("Pen")
    if pen_at < 0:
        return ""
    start = max(value.rfind(",", 0, pen_at), value.rfind(";", 0, pen_at)) + 1
    ends = [at for mark in (",", ";") if (at := value.find(mark, pen_at)) >= 0]
    segment = value[start:min(ends) if ends else len(value)].strip()
    parenthetical = re.search(r"\s*(\([^()]*\))\s*$", segment)
    if parenthetical:
        segment = segment[:parenthetical.start()].strip()
    words = segment.split()
    center = next((index for index, word in enumerate(words) if "Pen" in word), None)
    if center is None:
        return ""
    left = center
    while left and _starts_with_uppercase_or_digit(words[left - 1]):
        left -= 1
    right = center + 1
    while right < len(words) and _starts_with_uppercase_or_digit(words[right]):
        right += 1
    phrase = " ".join(words[left:right]).strip(" ,.;")
    if parenthetical:
        phrase += " " + parenthetical.group(1)
    return phrase


def pen_short_spec(values: list[str]) -> str:
    if len(values) == 1 and "purchase" in values[0].casefold():
        return values[0]
    has_no = any(value.lstrip().casefold().startswith("no") for value in values)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if "purchase" in value.casefold() or value.lstrip().casefold().startswith("no"):
            continue
        phrase = _pen_phrase(value)
        if not phrase:
            continue
        if has_no:
            phrase += "*"
        if phrase not in seen:
            seen.add(phrase)
            result.append(phrase)
    return "\n".join(result)
