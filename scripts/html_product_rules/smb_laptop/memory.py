from __future__ import annotations

import html
import re
from dataclasses import dataclass


MEMORY_FEATURE = "Memory"


@dataclass(frozen=True)
class HtmlMemoryResult:
    short_spec: str
    note: str


def clean_html_text(value: str, keep_sup: bool = False) -> str:
    if not keep_sup:
        value = re.sub(r"<sup\b.*?</sup>", "", value, flags=re.I | re.S)
        value = re.sub(
            r"<span\s+class=['\"]supText['\"][^>]*>.*?</span>",
            "",
            value,
            flags=re.I | re.S,
        )
    value = re.sub(
        r"<strong\s+class=['\"]as_note_type['\"][^>]*>.*?</strong>",
        "",
        value,
        flags=re.I | re.S,
    )
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"</(?:li|tr|p|div)>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(" ".join(value.split()))


def clean_note_text(value: str) -> str:
    return re.sub(r"^\s*[.;:]+\s*", "", clean_html_text(value)).strip()


def note_key(value: str) -> str:
    value = re.sub(r"^\s*[.;:]+\s*", "", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def extract_refs(value: str) -> list[str]:
    refs: list[str] = []
    for content in re.findall(
        r"<span\s+class=['\"]supText['\"][^>]*>(.*?)</span>",
        value,
        flags=re.I | re.S,
    ):
        for number in re.findall(r"\d+", html.unescape(content)):
            if number not in refs:
                refs.append(number)
    return refs


def memory_section(html_text: str) -> str:
    start = re.search(r"<h2\s+specStructure=['\"]Memory['\"][^>]*>", html_text, flags=re.I)
    if not start:
        return ""
    next_section = re.search(r"<h2\s+specStructure=", html_text[start.end() :], flags=re.I)
    end = start.end() + next_section.start() if next_section else len(html_text)
    return html_text[start.start() : end]


def note_map(section: str) -> dict[str, str]:
    notes: dict[str, str] = {}
    for match in re.finditer(
        r"<span\s+class=['\"]note_number['\"][^>]*>(.*?)</span>\s*<span>(.*?)</span>",
        section,
        flags=re.I | re.S,
    ):
        numbers = re.findall(r"\d+", html.unescape(clean_html_text(match.group(1), keep_sup=True)))
        text = clean_note_text(match.group(2))
        for number in numbers:
            notes[number] = text
    return notes


def feature_blocks(section: str) -> dict[str, dict[str, object]]:
    blocks: dict[str, dict[str, object]] = {}
    pattern = (
        r"<div\s+specStructure=['\"]Memory['\"][^>]*>(.*?)</div>"
        r"(?=<div\s+specStructure=['\"]Memory['\"]|<hr\b|<h2\b|$)"
    )
    for match in re.finditer(pattern, section, flags=re.I | re.S):
        block = match.group(1)
        heading_match = re.search(r"<h3[^>]*>(.*?)</h3>", block, flags=re.I | re.S)
        value_match = re.search(
            r"<div[^>]*class=['\"][^'\"]*divFeatureValue[^'\"]*['\"][^>]*>(.*)$",
            block,
            flags=re.I | re.S,
        )
        if not heading_match or not value_match:
            continue

        heading_html = heading_match.group(1)
        heading = re.sub(r"\[.*?\]|\*+", "", clean_html_text(heading_html)).strip()
        value_html = value_match.group(1)
        list_items = re.findall(r"<li[^>]*>(.*?)</li>", value_html, flags=re.I | re.S)
        if list_items:
            values: str | list[str] = [clean_html_text(item) for item in list_items]
            value_refs: list[str] | list[list[str]] = [extract_refs(item) for item in list_items]
        else:
            values = clean_html_text(value_html)
            value_refs = extract_refs(value_html)

        blocks[heading] = {
            "heading_refs": extract_refs(heading_html),
            "values": values,
            "value_refs": value_refs,
        }
    return blocks


def as_list(value: object) -> list[str]:
    return value if isinstance(value, list) else [str(value)]


def capacity_gb(value: str) -> float:
    capacities: list[float] = []
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(TB|GB)\b", value, flags=re.I):
        capacities.append(float(number) * (1024 if unit.casefold() == "tb" else 1))
    return max(capacities) if capacities else -1


def split_condition(value: str) -> tuple[str, str]:
    match = re.match(r"\s*([^:]+):\s*(.*)$", value)
    return (match.group(1).strip(), match.group(2).strip()) if match else ("", value.strip())


def condition_of(value: str) -> str:
    return split_condition(value)[0].casefold()


def first_before_comma(value: str) -> str:
    return value.split(",", 1)[0].strip()


def normalize_up_to_upper_body(value: str) -> str:
    _, body = split_condition(value)
    if re.match(r"^up to\b", body, flags=re.I):
        return re.sub(r"^up to\b", "Up to", body, count=1, flags=re.I)
    return "Up to " + body


def normalize_body_up_to_lower(body: str) -> str:
    body = body.strip()
    if re.match(r"^up to\b", body, flags=re.I):
        return re.sub(r"^up to\b", "up to", body, count=1, flags=re.I)
    return "up to " + body


def lower_initial_up_to(value: str) -> str:
    return re.sub(r"^Up to\b", "up to", value, count=1)


def cap_first(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def format_branch_lower_up_to(value: str) -> str:
    condition, body = split_condition(value)
    body = normalize_body_up_to_lower(body)
    return cap_first(f"{condition}: {body}" if condition else body)


def has_memory_type(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:LPDDR\dX?|DDR\d|LPCAMM2|SODIMM|CSODIMM|UDIMM|CUDIMM|RDIMM|DIMM)\b",
            value,
            flags=re.I,
        )
    )


def type_info(value: str) -> tuple[str, int, str]:
    _, body = split_condition(value.split(",", 1)[0].strip())
    first = body.strip()
    type_match = re.search(r"\b(LPDDR\dX?|DDR\d)\b", first, flags=re.I)
    base = type_match.group(1).upper() if type_match else first.upper()
    qualifiers: list[str] = []
    for qualifier in ["LPCAMM2", "SODIMM", "CSODIMM", "CUDIMM", "UDIMM", "RDIMM", "DIMM"]:
        if re.search(r"\b" + re.escape(qualifier) + r"\b", first, flags=re.I):
            qualifiers.append(qualifier)
    key = " ".join([base] + qualifiers)
    speed_match = re.search(r"-(\d{4,5})\b", first)
    speed = int(speed_match.group(1)) if speed_match else -1
    return key, speed, first


def highest_memory_types(memory_type_values: object) -> str:
    best: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for value in as_list(memory_type_values):
        key, speed, first = type_info(value)
        if key not in best:
            order.append(key)
        if key not in best or speed > best[key][0]:
            best[key] = (speed, first)
    return " / ".join(best[key][1] for key in order)


def memory_speed_line(memory_type_values: object) -> str:
    return "Memory speed up to " + highest_memory_types(memory_type_values)


def memory_type_values_for_branch(memory_type_values: object, branch: str) -> list[str]:
    values = as_list(memory_type_values)
    condition = condition_of(branch)
    if condition:
        matches = [value for value in values if condition_of(value) == condition]
        if matches:
            return matches
    unconditioned = [value for value in values if not condition_of(value)]
    return unconditioned or values


def ensure_not_upgradable_suffix(value: str) -> str:
    value = re.sub(r"\s*,?\s*not upgradable\b", "", value, flags=re.I).strip(" ,")
    return f"{value}, not upgradable" if value else "not upgradable"


def append_speed_before_not_upgradable(value: str, speed_line: str) -> str:
    value = ensure_not_upgradable_suffix(value)
    if not speed_line:
        return value
    return re.sub(
        r"\s*,\s*not upgradable\s*$",
        f", {speed_line}, not upgradable",
        value,
        count=1,
        flags=re.I,
    )


def memory_result(short_spec: str, notes: list[str]) -> HtmlMemoryResult:
    return HtmlMemoryResult(short_spec, "\n".join(note for note in notes if note))


def collect_memory_type_notes(block: dict[str, object], notes: dict[str, str]) -> list[str]:
    refs: list[str] = []
    refs.extend(block["heading_refs"])  # type: ignore[arg-type]
    if isinstance(block["values"], list):
        for item_refs in block["value_refs"]:  # type: ignore[union-attr]
            refs.extend(item_refs)
    else:
        refs.extend(block["value_refs"])  # type: ignore[arg-type]

    output: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref not in notes:
            continue
        key = note_key(notes[ref])
        if key and key not in seen:
            seen.add(key)
            output.append(notes[ref])
    return output


def has_systemboard_or_soldered(slot_values: list[str]) -> bool:
    return bool(re.search(r"\b(systemboard|soldered)\b", " ".join(slot_values), flags=re.I))


def has_usable_slot(value: str) -> bool:
    without_no_slots = re.sub(r"\bno slots?\b", "", value.casefold())
    return bool(re.search(r"\bslots?\b", without_no_slots))


def pick_max(values: list[str]) -> str:
    return max(values, key=capacity_gb)


def soldered_max_pred(value: str) -> bool:
    return bool(re.search(r"\b(not upgradable|soldered)\b", value, flags=re.I))


def pick_by_pred(values: list[str], predicate) -> str:
    matches = [value for value in values if predicate(value)]
    return pick_max(matches) if matches else ""


def match_slot_for_branch(slot_values: list[str], branch: str) -> str:
    condition = condition_of(branch)
    if condition:
        for slot_value in slot_values:
            if condition_of(slot_value) == condition:
                return first_before_comma(slot_value)
    for slot_value in slot_values:
        if has_usable_slot(slot_value) and not re.search(r"\b(systemboard|soldered)\b", slot_value, flags=re.I):
            return first_before_comma(slot_value)
    for slot_value in slot_values:
        if has_usable_slot(slot_value):
            return first_before_comma(slot_value)
    return first_before_comma(slot_values[0])


def combine_slot_and_branch(slot_text: str, branch_text: str) -> str:
    slot_condition, slot_body = split_condition(slot_text)
    branch_condition, branch_body = split_condition(branch_text)
    if slot_condition and branch_condition and slot_condition.casefold() == branch_condition.casefold():
        return f"{slot_condition}: {slot_body}, {branch_body}"
    return f"{slot_text}, {branch_text}"


def join_max_values(values: list[str]) -> str:
    return "; ".join(values)


def generate_memory_short_spec(html_text: str, product: str) -> HtmlMemoryResult | None:
    section = memory_section(html_text)
    if not section:
        return None
    memory = feature_blocks(section)
    required = {"Max Memory", "Memory Slots", "Memory Type"}
    if not required.issubset(memory):
        return None

    max_values = as_list(memory["Max Memory"]["values"])
    slot_values = as_list(memory["Memory Slots"]["values"])
    notes = note_map(section)
    memory_type_notes = collect_memory_type_notes(memory["Memory Type"], notes)
    if product.casefold().startswith("thinkstation"):
        return memory_result(join_max_values(max_values), memory_type_notes)

    if not has_systemboard_or_soldered(slot_values):
        short_spec = f"{first_before_comma(slot_values[0])}, {lower_initial_up_to(join_max_values(max_values))}"
        return memory_result(short_spec, memory_type_notes)

    if not any(has_usable_slot(value) for value in slot_values):
        best = pick_max(max_values)
        lines = [ensure_not_upgradable_suffix(normalize_up_to_upper_body(best))]
        if not has_memory_type(lines[0]):
            lines.append(memory_speed_line(memory["Memory Type"]["values"]))
        return memory_result("\n".join(lines), memory_type_notes)

    lines: list[str] = []
    soldered_branch = pick_by_pred(max_values, soldered_max_pred)
    if soldered_branch:
        soldered_line = format_branch_lower_up_to(soldered_branch)
        if has_memory_type(soldered_line):
            soldered_line = ensure_not_upgradable_suffix(soldered_line)
        else:
            soldered_line = append_speed_before_not_upgradable(
                soldered_line,
                memory_speed_line(memory_type_values_for_branch(memory["Memory Type"]["values"], soldered_branch)),
            )
        lines.append(soldered_line)
    nonsoldered_branch = pick_by_pred(max_values, lambda value: not soldered_max_pred(value))
    if nonsoldered_branch:
        branch_text = format_branch_lower_up_to(nonsoldered_branch)
        slot_text = match_slot_for_branch(slot_values, nonsoldered_branch)
        lines.append(cap_first(combine_slot_and_branch(slot_text, branch_text)))
    if not lines:
        lines.append(format_branch_lower_up_to(pick_max(max_values)))
    return memory_result("\n".join(lines), memory_type_notes)
