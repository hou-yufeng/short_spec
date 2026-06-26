from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

VENDOR_PDF_DEPS = Path(__file__).resolve().parent / "_storage_pdf_deps"
if VENDOR_PDF_DEPS.exists():
    sys.path.insert(0, str(VENDOR_PDF_DEPS))

from batch_generate_shortspec_excel import (
    GenerationResult,
    ProductSpec,
    collect_spec_paths,
    derive_display_name,
    derive_product_name,
    extract_pdf_texts,
    is_pdf_page_break,
    join_pdf_page_texts,
    normalize_text,
    save_generation_texts,
    write_xlsx,
)


@dataclass(frozen=True)
class StorageToolConfig:
    product_line: str
    generator_name: str
    runtime_text_dir: str
    generated_text_dir: str
    output_xlsx: str


@dataclass(frozen=True)
class StorageShortSpecResult:
    product_name: str
    marketing_name: str
    product_line: str
    storage_short_spec: str
    source_max_storage_support: str
    source_raid: str
    status: str
    source_storage_section: str


@dataclass(frozen=True)
class RenderedStorage:
    body: str
    raid_lines: tuple[str, ...] = ()
    status: str = "OK"


NEGATIVE_VALUES = {"", "-", "/", "N/A", "TBD", "None", "No support"}
PAGE_HEADER_TOKENS = {"psref", "product specifications", "reference"}

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

TOP_LEVEL_SECTIONS = {
    "OVERVIEW",
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "NETWORK",
    "SECURITY & PRIVACY",
    "MANAGEABILITY",
    "SERVICE",
    "ACCESSORIES",
    "OPERATING REQUIREMENTS",
    "CERTIFICATIONS",
    "SOFTWARE",
}

STOP_LABELS = {
    "Processor",
    "Processor Family",
    "Processor Name",
    "Operating System",
    "Graphics",
    "Integrated Graphics",
    "Discrete Graphics Support",
    "Monitor Support",
    "Chipset",
    "Memory",
    "Max Memory",
    "Memory Type",
    "Memory Slots",
    "Audio",
    "Multi-Media",
    "Camera",
    "Sensors",
    "Battery",
    "Power Adapter",
    "Display",
    "Touchscreen",
    "Screen-to-Body Ratio",
    "Multi-mode",
    "Pen",
    "Keyboard",
    "Touchpad",
    "Dimensions (WxDxH)",
    "Weight",
    "Case Color",
    "Color",
    "Case Material",
    "Buttons",
    "Mechanical",
    "Form Factor",
    "Bays",
    "M.2 Slots",
    "Expansion Slots",
    "EOU",
    "Stand",
    "Others",
    "Network",
    "WWAN",
    "SIM Card",
    "Cellular Bands",
    "Ethernet",
    "Onboard Ethernet",
    "Optional Ethernet",
    "NFC",
    "Wi-Fi Direct",
    "Wi-Fi Display",
    "Location Services",
    "Ports",
    "Front Ports",
    "Optional Front Ports",
    "Rear Ports",
    "Optional Rear Ports",
    "Top Ports",
    "Left Ports",
    "Right Ports",
    "Docking",
    "Security",
    "Security Chip",
    "Fingerprint Reader",
    "Physical Locks",
    "Chassis Intrusion Switch",
    "BIOS Security",
    "System Management",
    "Diagnostic",
    "Bundled Accessories",
    "Green Certifications",
    "Other Certifications",
    "Mil-Spec Test",
    "ISV Certifications",
    "Removable Storage",
}

INTERNAL_STORAGE_LABELS = {
    "Max Storage Support",
    "Storage Support",
    "Storage Slot",
    "Storage Slots",
    "Storage Type",
    "Storage Controllers",
    "Storage Controller",
    "RAID",
}

MAX_STORAGE_KEYS = {"max storage support", "storage support"}
RAID_KEYS = {"raid"}
CONTROLLER_KEYS = {"storage controllers", "storage controller"}
FIELD_STOP_KEYS = {label_key for label_key in ()}


def is_page_break_line(line: str) -> bool:
    return is_pdf_page_break(clean_line(line))


def clean_line(line: str) -> str:
    line = normalize_text(line)
    replacements = {
        "\ufeff": "",
        "\x00": "",
        "\x07": "",
        "\x0c": "\n",
        "\u00a0": " ",
        "\u00ae": "",
        "\u2122": "",
        "\u2022": " ",
        "\u2023": " ",
        "\u25e6": " ",
        "\u5e90": "",
        "\u9225?": " ",
        "\u9225": " ",
        "\u95b3?": "",
        "\u95b3": "",
        "\u6434?": "",
        "\u6434": "",
        "\u8e64?": "",
        "\ufffd": "",
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"\bTM\b", "", line)
    line = re.sub(r"\bPCIe\s+NVMe\b", "PCIe NVMe", line)
    line = re.sub(r"\bWi\s*-\s*Fi\b", "Wi-Fi", line, flags=re.I)
    line = line.replace("3.5''", '3.5"').replace("2.5''", '2.5"')
    line = line.replace("3.5\u201d", '3.5"').replace("2.5\u201d", '2.5"')
    line = line.replace("3.5\u2033", '3.5"').replace("2.5\u2033", '2.5"')
    line = re.sub(r'\b(2\.5|3\.5)\s*-?\s*inch\b', r'\1"', line, flags=re.I)
    line = re.sub(r'\b(2\.5|3\.5)"?\s*(HDD|SATA)\b', r'\1" \2', line, flags=re.I)
    line = re.sub(r'\b(2\.5|3\.5)"\s*HDD\s*Bay\b', r'\1" HDD bay', line, flags=re.I)
    line = re.sub(r'\b(2\.5|3\.5)\s+HDD\b', r'\1" HDD', line, flags=re.I)
    line = re.sub(r"\bM\.\s*2\b", "M.2", line)
    line = re.sub(r"(?<=\d)\s*/\s*(?=\d)", "/", line)
    line = re.sub(r"\s*\+\s*", " + ", line)
    line = re.sub(r"\s+", " ", line).strip(" \t\r\n-;")
    line = re.sub(r"^\?+\s*", "", line)
    return line


def split_lines(text: str) -> list[str]:
    normalized = normalize_text(text)
    for marker in ("\u2022", "\u2023", "\u25e6", "\u9225?"):
        normalized = normalized.replace(marker, "\n")
    return [clean_line(line) for line in normalized.splitlines() if clean_line(line)]


def label_key(line: str) -> str:
    line = clean_line(line)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"\*+$", "", line)
    line = re.sub(r"[^a-z0-9+&/(). -]+", "", line.lower())
    return re.sub(r"\s+", " ", line).strip(" :")


STOP_LABEL_KEYS = {label_key(label) for label in STOP_LABELS}
INTERNAL_STORAGE_KEYS = {label_key(label) for label in INTERNAL_STORAGE_LABELS}
TOP_LEVEL_SECTION_KEYS = {label_key(label) for label in TOP_LEVEL_SECTIONS}
FIELD_STOP_KEYS = INTERNAL_STORAGE_KEYS | {"notes", "notes:"} | STOP_LABEL_KEYS | TOP_LEVEL_SECTION_KEYS


def is_page_noise_line(line: str) -> bool:
    cleaned = clean_line(line)
    if not cleaned:
        return True
    if is_page_break_line(cleaned):
        return True
    lowered = cleaned.lower()
    token = label_key(cleaned)
    if cleaned in NEGATIVE_VALUES:
        return True
    if token in PAGE_HEADER_TOKENS:
        return True
    if re.search(r"\b\d+\s+of\s+\d+", lowered):
        return True
    if "product specifications reference" in lowered:
        return True
    if lowered.startswith(("feature with ", "items with ", "please refer", "lenovo reserves", "for more information")):
        return True
    if lowered.startswith(("for detailed information", "the specifications on this page", "actual ")):
        return True
    if lowered.startswith(("http://", "https://")):
        return True
    return False


def is_page_title_before_header(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    if label_key(lines[index + 1]) != "psref":
        return False
    current = clean_line(lines[index])
    if re.search(r"\b(?:SSD|HDD|UFS|eMMC|drive|Storage)\b", current, flags=re.I):
        return False
    return bool(re.search(r"\d", current))


def is_storage_stop_line(line: str) -> bool:
    key = label_key(line)
    if key in {"storage"}:
        return False
    if key in INTERNAL_STORAGE_KEYS:
        return False
    if key in {"notes", "notes:"}:
        return True
    if key in TOP_LEVEL_SECTION_KEYS:
        return True
    return key in STOP_LABEL_KEYS


def extract_storage_section(spec_text: str) -> list[str]:
    lines = split_lines(spec_text)
    for index, line in enumerate(lines):
        if label_key(line) != "storage":
            continue

        section: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            line = lines[cursor]
            if is_page_noise_line(line) or is_page_title_before_header(lines, cursor):
                cursor += 1
                continue
            if is_storage_stop_line(line):
                break
            section.append(line)
            cursor += 1
        return section
    return []


def is_field_stop(line: str, allowed_labels: set[str]) -> bool:
    key = label_key(line)
    if key in allowed_labels:
        return False
    if key in FIELD_STOP_KEYS:
        return True
    return False


def collect_field(section: list[str], label_keys: set[str]) -> list[str]:
    for index, line in enumerate(section):
        if label_key(line) not in label_keys:
            continue
        values: list[str] = []
        cursor = index + 1
        while cursor < len(section):
            line = section[cursor]
            key = label_key(line)
            if key in label_keys and not values:
                cursor += 1
                continue
            if is_field_stop(line, label_keys):
                break
            if not is_page_noise_line(line):
                values.append(line)
            cursor += 1
        return normalize_storage_tokens(values)
    return []


def collect_storage_controllers(section: list[str]) -> list[str]:
    for index, line in enumerate(section):
        if label_key(line) not in CONTROLLER_KEYS:
            continue
        values: list[str] = []
        cursor = index + 1
        while cursor < len(section):
            line = section[cursor]
            key = label_key(line)
            if key in {"notes", "notes:"} or key in STOP_LABEL_KEYS or key in TOP_LEVEL_SECTION_KEYS:
                break
            if key in INTERNAL_STORAGE_KEYS and key not in CONTROLLER_KEYS:
                break
            if not is_page_noise_line(line):
                values.append(line)
            cursor += 1
        return normalize_storage_tokens(values)
    return []


def normalize_storage_tokens(tokens: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for token in tokens:
        cleaned = normalize_storage_phrase(token)
        if not cleaned or cleaned in NEGATIVE_VALUES:
            continue
        if cleaned == "?":
            continue
        if normalized and should_merge_storage_continuation(normalized[-1], cleaned):
            normalized[-1] = normalize_storage_phrase(f"{normalized[-1]} {cleaned}")
        else:
            normalized.append(cleaned)
    return normalized


def should_merge_storage_continuation(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if label_key(current) in FIELD_STOP_KEYS or starts_drive_summary(current):
        return False
    if previous.endswith((",", "+", "/", " and", " or")):
        return True
    current_words = current.split()
    if len(current_words) <= 4 and current[:1].islower() and re.search(r"\b(?:M\.2|SSD|HDD|SATA|PCIe)\b", previous, flags=re.I):
        return True
    return False


def normalize_storage_phrase(value: str) -> str:
    value = clean_line(value)
    value = re.sub(r"\*+$", "", value)
    value = re.sub(r"\bNo\s+support\b", "No support", value, flags=re.I)
    value = re.sub(
        r'\bopen\s+(2\.5|3\.5)"\s*HDD\s*bay\b',
        lambda match: f'open {match.group(1)}" HDD bay',
        value,
        flags=re.I,
    )
    value = re.sub(r"\bHDD\s+Bay\b", "HDD bay", value, flags=re.I)
    value = re.sub(r"\bUFS\s+on\s+systemboard\b", "UFS on systemboard", value, flags=re.I)
    value = re.sub(r"\bMicroSD\b", "microSD", value, flags=re.I)
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",\s*,", ",", value)
    value = re.sub(r"\s+", " ", value).strip(" ,.;")
    value = re.sub(r"\.$", "", value)
    return value


def is_monitor_product(product_name: str, marketing_name: str, spec_text: str) -> bool:
    combined = f"{product_name} {marketing_name} {spec_text[:1000]}".lower()
    return "thinkvision" in combined or re.search(r"\bmonitor\b", combined) is not None


def is_raid_support_line(line: str) -> bool:
    lowered = clean_line(line).lower()
    return "raid" in lowered and "support" in lowered and "no support" not in lowered


def should_drop_max_line(line: str) -> bool:
    lowered = clean_line(line).lower()
    if not lowered or lowered in {value.lower() for value in NEGATIVE_VALUES}:
        return True
    if lowered.startswith(("to install ", "the storage capacity supported", "the max capacity", "the system may support")):
        return True
    if lowered.startswith(("for certain post-manufacturing", "available storage", "storage capacity supported")):
        return True
    if "only for customer self upgrade" in lowered:
        return True
    if "customer self upgrade purpose" in lowered:
        return True
    return False


def is_condition_label(value: str) -> bool:
    cleaned = clean_line(value).strip(" :")
    lowered = cleaned.lower()
    if not cleaned:
        return False
    if re.match(r"^(?:up to|one drive|two drives)", lowered):
        return False
    if re.search(r"\b(?:ssd|hdd|emmc|ufs|flash|sata|m\.2)\b", lowered):
        return False
    return any(
        marker in lowered
        for marker in (
            "model",
            "models",
            "battery",
            "graphics",
            "platform",
            "wh",
            "uma",
            "discrete",
            "intel",
            "amd",
            "nvidia",
            "rtx",
            "lake",
            "processor",
            "processors",
            "with",
            "without",
        )
    )


def split_condition_line(line: str) -> tuple[str, str] | None:
    cleaned = clean_line(line).strip()
    match = re.match(r"^(?P<condition>[^:]{1,140}):\s*(?P<rest>.*)$", cleaned)
    if not match:
        return None
    condition = normalize_storage_phrase(match.group("condition"))
    if not is_condition_label(condition):
        return None
    return condition, normalize_storage_phrase(match.group("rest"))


def is_condition_heading(line: str) -> bool:
    split = split_condition_line(line)
    return split is not None and not split[1]


def split_condition_branches(lines: list[str]) -> list[tuple[str, list[str]]]:
    branches: list[tuple[str, list[str]]] = []
    condition = ""
    current: list[str] = []
    for line in lines:
        split = split_condition_line(line)
        if split is not None:
            if current:
                branches.append((condition, current))
            condition, rest = split
            current = [rest] if rest else []
        else:
            current.append(line)
    if current:
        branches.append((condition, current))
    return branches


def parse_number(value: str) -> int | None:
    lowered = value.lower()
    if lowered.isdigit():
        return int(lowered)
    return NUMBER_WORDS.get(lowered)


def drive_count_score(text: str) -> int:
    lowered = text.lower()
    matches = re.findall(r"\bup to\s+([a-z]+|\d+)\s+drives?\b", lowered)
    counts = [parse_number(match) for match in matches]
    numeric_counts = [count for count in counts if count is not None]
    if numeric_counts:
        return max(numeric_counts)
    match = re.search(r"\bone\s+drive\b", lowered)
    if match:
        return 1
    option_scores: list[int] = []
    for option in re.split(r"\s*,?\s+or\s+", lowered):
        qty_matches = [int(value) for value in re.findall(r"\b(\d+)x\b", option)]
        if qty_matches:
            option_scores.append(sum(qty_matches))
    if option_scores:
        return max(option_scores)
    return 1 if re.search(r"\b(?:ufs|emmc|flash|ssd|hdd)\b", lowered) else 0


def branch_drive_count_score(lines: list[str], rendered_body: str) -> int:
    raw_score = drive_count_score(" ".join(lines))
    rendered_score = drive_count_score(rendered_body)
    return max(raw_score, rendered_score)


def capacity_score(text: str) -> float:
    score = 0.0
    for value, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(TB|GB)\b", text, flags=re.I):
        amount = float(value)
        if unit.lower() == "tb":
            amount *= 1024
        score = max(score, amount)
    return score


def capacity_to_gb(value: str, unit: str) -> float:
    amount = float(value)
    return amount * 1024 if unit.lower() == "tb" else amount


def capacity_token_to_gb(value: str) -> float | None:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(TB|GB)", normalize_storage_phrase(value), flags=re.I)
    if not match:
        return None
    return capacity_to_gb(match.group(1), match.group(2))


def format_capacity_gb(amount_gb: float) -> str:
    if amount_gb >= 1024:
        return f"{format_capacity_number(amount_gb / 1024)}TB"
    return f"{format_capacity_number(amount_gb)}GB"


def format_capacity_number(value: float) -> str:
    if abs(value - round(value)) < 0.001:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def strip_each_capacity_clauses(value: str) -> str:
    value = re.sub(r",\s*\d+(?:\.\d+)?\s*(?:TB|GB)\s+each\b", "", value, flags=re.I)
    value = re.sub(
        r"\b(\d+(?:\.\d+)?)\s*(TB|GB)\s+each\b",
        lambda match: f"{match.group(1)}{match.group(2).upper()}",
        value,
        flags=re.I,
    )
    return value


def drive_quantity(part: str) -> int | None:
    counts = [int(value) for value in re.findall(r"\b(\d+)\s*x\b", part, flags=re.I)]
    if counts:
        return max(counts)

    match = re.search(r"\b(?:up to\s+)?([a-z]+|\d+)\s+(?:M\.2|[23]\.5\"|SATA)\b", part, flags=re.I)
    if match:
        return parse_number(match.group(1).lower())
    return None


def detail_capacity_for_same_type(detail: str) -> tuple[float, str, int | None] | None:
    detail = normalize_storage_phrase(detail)
    detail = re.sub(r",\s*for\b.*$", "", detail, flags=re.I)

    total_each = re.search(
        r"\bup to\s+\d+(?:\.\d+)?\s*(?:TB|GB)\s*,\s*(\d+(?:\.\d+)?)\s*(TB|GB)\s+each\b",
        detail,
        flags=re.I,
    )
    if total_each:
        return capacity_to_gb(total_each.group(1), total_each.group(2)), "per_drive", None

    counted_capacity = re.search(
        r"\bup to\s+(\d+)\s*,\s*up to\s+(\d+(?:\.\d+)?)\s*(TB|GB)(?:\s+each)?\b",
        detail,
        flags=re.I,
    )
    if counted_capacity:
        mode = "per_drive" if "each" in counted_capacity.group(0).lower() else "total"
        return (
            capacity_to_gb(counted_capacity.group(2), counted_capacity.group(3)),
            mode,
            int(counted_capacity.group(1)),
        )

    each_capacity = re.search(
        r"\bup to\s+(\d+(?:\.\d+)?)\s*(TB|GB)\s+each\b",
        detail,
        flags=re.I,
    )
    if each_capacity:
        return capacity_to_gb(each_capacity.group(1), each_capacity.group(2)), "per_drive", None

    capacities = list(re.finditer(r"\bup to\s+(\d+(?:\.\d+)?)\s*(TB|GB)\b", detail, flags=re.I))
    if capacities:
        capacity = capacities[-1]
        return capacity_to_gb(capacity.group(1), capacity.group(2)), "total", None
    return None


def slot_specific_index(detail: str) -> int | None:
    ordinal_numbers = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
    }
    match = re.search(
        r"\bfor\s+(?:the\s+)?(?P<slot>first|second|third|fourth|fifth|sixth|\d+(?:st|nd|rd|th)?)\s+"
        r"(?:storage|drive|slot|ssd)\b",
        detail,
        flags=re.I,
    )
    if not match:
        return None
    slot = match.group("slot").lower()
    if slot in ordinal_numbers:
        return ordinal_numbers[slot]
    numeric = re.match(r"\d+", slot)
    return int(numeric.group(0)) if numeric else None


def is_slot_specific_capacity(detail: str, mode: str) -> bool:
    lowered = detail.lower()
    if mode != "total":
        return False
    if "each" in lowered or re.search(r"\btotal\b", lowered):
        return False
    return slot_specific_index(detail) is not None


def same_type_total_capacity(quantity: int, details: list[str]) -> float | None:
    total_capacities: list[float] = []
    per_drive_capacities: list[float] = []
    slot_capacities: dict[int, float] = {}

    for detail in details:
        parsed = detail_capacity_for_same_type(detail)
        if parsed is None:
            continue
        capacity_gb, mode, detail_count = parsed
        slot_index = slot_specific_index(detail)
        if slot_index is not None and is_slot_specific_capacity(detail, mode):
            slot_capacities[slot_index] = max(slot_capacities.get(slot_index, 0.0), capacity_gb)
        elif mode == "total":
            total_capacities.append(capacity_gb)
        elif detail_count is not None:
            total_capacities.append(capacity_gb * min(quantity, detail_count))
        else:
            per_drive_capacities.append(capacity_gb)

    calculated_capacities = list(total_capacities)
    if slot_capacities:
        selected = sorted(slot_capacities.values(), reverse=True)[:quantity]
        if selected:
            calculated_capacities.append(sum(selected))
    if per_drive_capacities:
        if len(per_drive_capacities) == 1:
            calculated_capacities.append(per_drive_capacities[0] * quantity)
        else:
            sorted_capacities = sorted(per_drive_capacities, reverse=True)
            selected = sorted_capacities[:quantity]
            if len(selected) < quantity:
                selected.extend([sorted_capacities[0]] * (quantity - len(selected)))
            calculated_capacities.append(sum(selected))

    return max(calculated_capacities) if calculated_capacities else None


def same_type_capacity_suffix(part: str, details: list[str]) -> str:
    quantity = drive_quantity(part)
    if quantity is None or quantity <= 1:
        return ""
    capacity_gb = same_type_total_capacity(quantity, details)
    if capacity_gb is None:
        return ""
    return f"{format_capacity_gb(capacity_gb)} total"


def capacity_total_suffix(value: str) -> str:
    match = re.search(r"\bup to\s+(\d+(?:\.\d+)?)\s*(TB|GB)\b", value, flags=re.I)
    if not match:
        return ""
    return f"{match.group(1)}{match.group(2).upper()} total"


def format_capacity_total_phrase(value: str) -> str:
    return re.sub(
        r"\s+up to\s+(\d+(?:\.\d+)?)\s*(TB|GB)\b",
        lambda match: f", {match.group(1)}{match.group(2).upper()} total",
        value,
        flags=re.I,
    )


def count_word_to_int(value: str) -> int | None:
    return parse_number(value.lower())


def normalize_up_to_device_count(value: str) -> str:
    def replace_count(match: re.Match[str]) -> str:
        count = count_word_to_int(match.group("count"))
        if count is None:
            return match.group(0)
        return f"Up to {count}x "

    return re.sub(
        r"\bUp to\s+(?P<count>[a-z]+|\d+)\s+(?=(?:M\.2|[23]\.5\"|SATA))",
        replace_count,
        value,
        flags=re.I,
    )


def format_one_drive_capacity_first(value: str) -> str:
    def replace_drive(match: re.Match[str]) -> str:
        count = count_word_to_int(match.group("count"))
        if count is None:
            return match.group(0)
        capacity = f"{match.group('capacity')}{match.group('unit').upper()} total"
        device = normalize_storage_phrase(match.group("device"))
        return f"Up to {count}x {device}, {capacity}"

    return re.sub(
        r"\b(?P<count>one|two|\d+)\s+drives?,\s*up to\s+"
        r"(?P<capacity>\d+(?:\.\d+)?)\s*(?P<unit>TB|GB)\s+"
        r"(?P<device>[^,;]+?)(?=$|[,;])",
        replace_drive,
        value,
        flags=re.I,
    )


def format_storage_output_body(value: str) -> str:
    value = re.sub(r"^Storage:\s*", "", value, flags=re.I)
    value = format_one_drive_capacity_first(value)
    value = re.sub(r"\bUp to\s+(?:[a-z]+|\d+)\s+drives?:\s*", "Up to ", value, flags=re.I)
    value = re.sub(r",\s*or\s+(?:[a-z]+|\d+)\s+drives?:\s*", ", or ", value, flags=re.I)
    value = normalize_up_to_device_count(value)
    value = re.sub(
        r"\s*;\s*up to\s+(\d+(?:\.\d+)?)\s*(TB|GB)\b",
        lambda match: f", {match.group(1)}{match.group(2).upper()} total",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\s*,\s*up to\s+(\d+(?:\.\d+)?)\s*(TB|GB)\b",
        lambda match: f", {match.group(1)}{match.group(2).upper()} total",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"(?P<device>\b\d+x\s+[^,;+;]+?)\s+up to\s+(?P<capacity>\d+(?:\.\d+)?)\s*(?P<unit>TB|GB)\b",
        lambda match: f"{match.group('device')}, {match.group('capacity')}{match.group('unit').upper()} total",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"(?P<device>\b(?:M\.2(?:\s+\d{4})?\s+SSD|SATA\s+HDD|SATA\s+SSD|[23]\.5\"\s+(?:SATA\s+)?HDD|[23]\.5\"\s+(?:SATA\s+)?SSD))\s+up to\s+"
        r"(?P<capacity>\d+(?:\.\d+)?)\s*(?P<unit>TB|GB)\b",
        lambda match: f"{match.group('device')}, {match.group('capacity')}{match.group('unit').upper()} total",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\s+up to\s+(\d+(?:\.\d+)?)\s*(TB|GB)\b",
        lambda match: f", {match.group(1)}{match.group(2).upper()} total",
        value,
        flags=re.I,
    )
    value = re.sub(r",\s*,", ",", value)
    return value


def strip_m2_size_tokens(value: str) -> str:
    return re.sub(r"\bM\.2\s+(?:\d{4}(?:/\d{4})*)\s+", "M.2 ", value, flags=re.I)


def finalize_direct_storage_body(value: str) -> str:
    value = normalize_storage_phrase(value)
    value = strip_m2_size_tokens(value)
    value = re.sub(r"\s*;\s*", "; ", value)
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"\s+\+\s+", " + ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,.;")
    return value


def render_max_storage(max_lines: list[str]) -> RenderedStorage:
    raid_lines = tuple(line for line in max_lines if is_raid_support_line(line))
    tokens = [line for line in max_lines if not is_raid_support_line(line)]
    service_upgrade = any("service upgrade" in line.lower() for line in tokens)
    tokens = [
        line
        for line in tokens
        if not should_drop_max_line(line)
        or "customer self upgrade" in line.lower()
        or "service upgrade" in line.lower()
    ]

    if not tokens:
        return RenderedStorage("", raid_lines, "Max Storage Support not found")

    branches = split_condition_branches(tokens)
    if len(branches) > 1:
        rendered_branches: list[tuple[int, float, str, RenderedStorage]] = []
        for condition, branch_lines in branches:
            rendered = render_storage_branch(branch_lines)
            if not rendered.body:
                continue
            rendered_branches.append(
                (
                    branch_drive_count_score(branch_lines, rendered.body),
                    capacity_score(rendered.body),
                    condition,
                    rendered,
                )
            )
        if not rendered_branches:
            return RenderedStorage("", raid_lines, "Ambiguous storage rules")
        rendered_branches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        top = rendered_branches[0]
        branch_raid = tuple(unique_preserve([*raid_lines, *top[3].raid_lines]))
        return RenderedStorage(top[3].body, branch_raid, top[3].status)

    rendered = render_storage_branch(branches[0][1] if branches else tokens)
    return RenderedStorage(rendered.body, tuple(unique_preserve([*raid_lines, *rendered.raid_lines])), rendered.status)


def render_storage_branch(lines: list[str]) -> RenderedStorage:
    lines = normalize_storage_tokens(lines)
    if not lines:
        return RenderedStorage("", (), "Max Storage Support not found")

    if looks_like_systemboard_storage(lines):
        body = render_systemboard_storage(lines)
    elif starts_drive_summary(lines[0]):
        body = render_drive_summary(lines[0], lines[1:])
    elif len(lines) == 1:
        body = normalize_storage_phrase(lines[0])
    else:
        body = render_mixed_storage_options(lines)

    if not body:
        return RenderedStorage("", (), "Ambiguous storage rules")
    return RenderedStorage(finalize_storage_body(body))


def starts_drive_summary(line: str) -> bool:
    return bool(
        re.match(
            r"^(?:up to\s+(?:[a-z]+|\d+)\s+drives?|one drive|two drives|"
            r"up to\s+(?:\d+\s*x|[a-z]+|\d+)\s+(?:M\.2|[23]\.5\"|SATA|SSD|HDD)\b)",
            normalize_storage_phrase(line),
            flags=re.I,
        )
    )


def looks_like_systemboard_storage(lines: list[str]) -> bool:
    return any(
        re.search(r"\b(?:UFS|eMMC|Flash Memory|Flash Storage|microSD)\b", line, flags=re.I)
        for line in lines
    )


def render_systemboard_storage(lines: list[str]) -> str:
    board_groups: dict[str, list[str]] = {}
    other_board: list[str] = []
    removable: list[str] = []
    drive_options: list[str] = []

    for line in lines:
        lowered = line.lower()
        if "microsd" in lowered or "card supports" in lowered or "card, supports" in lowered:
            removable.append(render_removable_storage(line))
            continue
        if starts_drive_summary(line):
            drive_options.append(render_drive_summary(line, []))
            continue
        match = re.match(
            r"^(?P<caps>(?:\d+(?:GB|TB)(?:/\d+(?:GB|TB))*))\s+(?P<tech>(?:UFS|eMMC|Flash Memory|Flash Storage)(?:\s+[0-9.]+)?)\s+on systemboard$",
            line,
            flags=re.I,
        )
        if match:
            tech = normalize_systemboard_storage_label(match.group("tech"))
            board_groups.setdefault(tech, []).extend(match.group("caps").split("/"))
        else:
            other_board.append(line)

    board_parts = []
    for tech, caps in board_groups.items():
        capacity_gb = max(
            (capacity for capacity in (capacity_token_to_gb(cap) for cap in caps) if capacity is not None),
            default=None,
        )
        if capacity_gb is not None:
            board_parts.append(f"{tech}, {format_capacity_gb(capacity_gb)} total")
        else:
            board_parts.append(f"{'/'.join(unique_preserve(caps))} {tech} on systemboard")
    board_parts.extend(other_board)

    primary_parts = [part for part in board_parts if part]
    for option in drive_options:
        if primary_parts:
            primary_parts.append(lower_first(option))
        else:
            primary_parts.append(option)

    removable = unique_preserve(part for part in removable if part)
    if removable:
        primary_parts.extend(removable)
    return " + ".join(unique_preserve(part for part in primary_parts if part))


def normalize_systemboard_storage_label(tech: str) -> str:
    tech = normalize_storage_phrase(tech)
    if re.search(r"\bUFS\b", tech, flags=re.I):
        return "UFS"
    if re.search(r"\beMMC\b", tech, flags=re.I):
        return "eMMC"
    if re.search(r"\bFlash Memory\b", tech, flags=re.I):
        return "Flash Memory"
    if re.search(r"\bFlash Storage\b", tech, flags=re.I):
        return "Flash Storage"
    return tech


def render_removable_storage(line: str) -> str:
    value = normalize_storage_phrase(line)
    value = re.sub(r"\s*\((?:exFAT|FAT32|NTFS)[^)]+\)", "", value, flags=re.I)
    value = re.sub(r"\s*\((?:exFAT|FAT32|NTFS)\)", "", value, flags=re.I)
    if re.search(r"\bmicroSD\b", value, flags=re.I):
        capacity_gb = removable_storage_capacity(value)
        if capacity_gb is not None:
            return f"microSD card, {format_capacity_gb(capacity_gb)} total"
        return "microSD card"
    return normalize_storage_phrase(value)


def removable_storage_capacity(value: str) -> float | None:
    quantity = removable_storage_quantity(value)
    capacity_gb = same_type_total_capacity(max(quantity, 1), [value])
    if capacity_gb is not None:
        return capacity_gb
    capacities = [
        capacity_to_gb(match.group(1), match.group(2))
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(TB|GB)\b", value, flags=re.I)
    ]
    return max(capacities) if capacities else None


def removable_storage_quantity(value: str) -> int:
    counts = [int(count) for count in re.findall(r"\b(\d+)\s*x\s+microSD\b", value, flags=re.I)]
    counts.extend(
        count
        for count in (
            parse_number(match.lower())
            for match in re.findall(r"\b(?:up to\s+)?([a-z]+|\d+)\s+microSD\b", value, flags=re.I)
        )
        if count is not None
    )
    return max(counts) if counts else 1


def render_mixed_storage_options(lines: list[str]) -> str:
    rendered: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if starts_drive_summary(line):
            details: list[str] = []
            cursor = index + 1
            while cursor < len(lines) and not starts_drive_summary(lines[cursor]):
                details.append(lines[cursor])
                cursor += 1
            rendered.append(render_drive_summary(line, details))
            index = cursor
            continue
        rendered.append(line)
        index += 1
    if not rendered:
        return ""
    return ", or ".join(rendered)


def render_drive_summary(base: str, details: list[str]) -> str:
    base = normalize_drive_base(base)
    details = [normalize_storage_phrase(detail) for detail in details if normalize_storage_phrase(detail)]
    service_upgrade = any("service upgrade" in detail.lower() for detail in details)
    details = [
        detail
        for detail in details
        if not should_drop_max_line(detail)
        or "customer self upgrade" in detail.lower()
        or "service upgrade" in detail.lower()
    ]

    if is_workstation_storage(base, details):
        summary = render_workstation_storage(base, details)
    elif re.search(r"\s\+\s", base):
        summary = render_plus_combo(base, details)
    else:
        summary = attach_single_drive_detail(base, details)

    if service_upgrade:
        summary = f"{summary}; second slot service-upgrade only"
    return finalize_storage_body(summary)


def normalize_drive_base(base: str) -> str:
    base = normalize_storage_phrase(base)
    base = re.sub(
        r"^(Up to\s+(?:[a-z]+|\d+)\s+drives?)\s*,\s*(.+)$",
        lambda match: f"{match.group(1)}: {match.group(2)}",
        base,
        flags=re.I,
    )
    base = re.sub(
        r"^(Up to\s+\d+\s+drives?)\s*\(([^)]+)\)",
        lambda match: f"{match.group(1)}: {match.group(2)}",
        base,
        flags=re.I,
    )
    base = re.sub(
        r";\s*or\s*(\d+\s+drives?)\s*\(([^)]+)\)",
        lambda match: f", or {match.group(1)}: {match.group(2)}",
        base,
        flags=re.I,
    )
    return normalize_storage_phrase(base)


def is_workstation_storage(base: str, details: list[str]) -> bool:
    lowered = f"{base} {' '.join(details)}".lower()
    if "sata hdd / ssd" in lowered or "front access" in lowered or "flex bay" in lowered:
        return True
    if any(re.search(r"\bgen\s+[45]\s+m\.2\s+ssd\b", detail, flags=re.I) for detail in details):
        return True
    return len(details) > 3 and "sata" in lowered


def render_workstation_storage(base: str, details: list[str]) -> str:
    base = normalize_storage_phrase(base)
    summarized = summarize_workstation_details(base, details)
    if summarized:
        return f"{base}; {'; '.join(summarized)}"
    return base


def summarize_workstation_details(base: str, details: list[str]) -> list[str]:
    summarized: list[str] = []
    m2_details: list[str] = []
    for detail in details:
        cleaned = normalize_storage_phrase(detail)
        if is_m2_ssd_detail(cleaned):
            m2_details.append(cleaned)
            continue
        capacity_summary = summarize_capacity_detail(cleaned)
        if capacity_summary:
            summarized.append(capacity_summary)
            continue
        cleaned = re.sub(r"\bup to\s+\d+,\s+up to\b", "up to", cleaned, flags=re.I)
        cleaned = re.sub(r",\s*for\b.*$", "", cleaned, flags=re.I)
        summarized.append(strip_each_capacity_clauses(cleaned))

    if m2_details:
        quantity = max_m2_quantity(base) or max_detail_quantity(m2_details) or len(m2_details)
        capacity_gb = same_type_total_capacity(max(quantity, 1), m2_details)
        if capacity_gb is not None:
            summarized.append(f"M.2 SSD, {format_capacity_gb(capacity_gb)} total")
        else:
            summarized.extend(strip_each_capacity_clauses(detail) for detail in m2_details)
    return unique_preserve(summarized)


def summarize_capacity_detail(detail: str, fallback_quantity: int | None = None) -> str:
    parsed = detail_capacity_for_same_type(detail)
    if parsed is None:
        return ""

    capacity_gb, mode, detail_count = parsed
    if mode == "per_drive":
        quantity = detail_count or fallback_quantity or 1
        capacity_gb *= quantity

    label = normalize_capacity_detail_label(detail)
    if not label:
        return ""
    return f"{label}, {format_capacity_gb(capacity_gb)} total"


def normalize_capacity_detail_label(detail: str) -> str:
    label = normalize_storage_phrase(detail)
    label = re.sub(r",\s*for\b.*$", "", label, flags=re.I)
    label = re.sub(
        r"\s+up to\s+\d+\s*,\s*up to\s+\d+(?:\.\d+)?\s*(?:TB|GB)(?:\s+each)?\b",
        "",
        label,
        flags=re.I,
    )
    label = re.sub(r"\s+up to\s+\d+(?:\.\d+)?\s*(?:TB|GB)(?:\s+each)?\b", "", label, flags=re.I)
    return normalize_storage_phrase(label)


def is_m2_ssd_detail(value: str) -> bool:
    return bool(re.search(r"\bM\.2(?:\s+\d{4})?\s+SSD\b", value, flags=re.I))


def max_m2_quantity(value: str) -> int | None:
    counts = [int(count) for count in re.findall(r"\b(\d+)x\s+M\.2\b", value, flags=re.I)]
    counts.extend(
        count
        for count in (parse_number(match.lower()) for match in re.findall(r"\bup to\s+([a-z]+|\d+)\s+M\.2\b", value, flags=re.I))
        if count is not None
    )
    return max(counts) if counts else None


def max_detail_quantity(details: list[str]) -> int | None:
    counts: list[int] = []
    for detail in details:
        for match in re.findall(r"\bup to\s+(\d+)\s*,\s*up to\s+\d+(?:\.\d+)?\s*(?:TB|GB)\b", detail, flags=re.I):
            counts.append(int(match))
    return max(counts) if counts else None


def render_plus_combo(base: str, details: list[str]) -> str:
    prefix, combo = split_summary_prefix(base)
    parts = re.split(r"\s+\+\s+", combo)
    used_indexes: set[int] = set()
    rendered_parts: list[str] = []

    for part in parts:
        part = normalize_drive_part(part)
        candidates = matching_detail_indexes(part, details)
        matching_details = [details[index] for index in candidates]
        multi_suffix = same_type_capacity_suffix(part, matching_details)
        if multi_suffix:
            rendered_parts.append(f"{part}, {multi_suffix}")
            used_indexes.update(candidates)
            continue
        suffixes = [capacity_suffix(details[index]) for index in candidates]
        suffixes = [suffix for suffix in suffixes if suffix]
        if suffixes and len({suffix.lower() for suffix in suffixes}) == 1:
            rendered_parts.append(f"{part}, {suffixes[0]}")
            used_indexes.update(candidates)
        elif needs_bay_suffix(part, candidates, details):
            rendered_parts.append(ensure_bay_part(part))
            used_indexes.update(candidates)
        else:
            rendered_parts.append(part)

    tail_details: list[str] = []
    for index, detail in enumerate(details):
        if index in used_indexes:
            continue
        if should_drop_max_line(detail):
            continue
        suffix = compact_detail(detail)
        if suffix:
            tail_details.append(suffix)

    rendered_parts = sort_open_bay_parts_last(rendered_parts)
    combo_text = " + ".join(rendered_parts)
    summary = f"{prefix}: {combo_text}" if prefix else combo_text
    if tail_details:
        summary = f"{summary}; {'; '.join(unique_preserve(tail_details))}"
    return normalize_storage_phrase(summary)


def split_summary_prefix(base: str) -> tuple[str, str]:
    match = re.match(r"^(Up to\s+(?:[a-z]+|\d+)\s+drives?|Two drives|One drive):\s*(.+)$", base, flags=re.I)
    if match:
        return match.group(1), match.group(2)
    return "", base


def normalize_drive_part(part: str) -> str:
    part = normalize_storage_phrase(part)
    part = re.sub(
        r'\bopen\s+(2\.5|3\.5)"\s*HDD(?!\s+bay)\b',
        lambda match: f'open {match.group(1)}" HDD bay',
        part,
        flags=re.I,
    )
    return part


def sort_open_bay_parts_last(parts: list[str]) -> list[str]:
    bay_parts = [part for part in parts if re.search(r"\b(?:open|bay)\b", part, flags=re.I)]
    regular_parts = [part for part in parts if part not in bay_parts]
    return [*regular_parts, *bay_parts]


def matching_detail_indexes(part: str, details: list[str]) -> list[int]:
    lowered = part.lower()
    indexes: list[int] = []
    for index, detail in enumerate(details):
        detail_lowered = detail.lower()
        if "up to" not in detail_lowered and "service upgrade" not in detail_lowered and "customer self upgrade" not in detail_lowered:
            continue
        if '3.5"' in lowered and '3.5"' in detail_lowered:
            indexes.append(index)
        elif '2.5"' in lowered and '2.5"' in detail_lowered:
            indexes.append(index)
        elif "m.2" in lowered and "m.2" in detail_lowered:
            indexes.append(index)
        elif "sata hdd" in lowered and "sata hdd" in detail_lowered:
            indexes.append(index)
        elif "sata ssd" in lowered and "sata ssd" in detail_lowered:
            indexes.append(index)
    return indexes


def capacity_suffix(detail: str) -> str:
    detail = normalize_storage_phrase(detail)
    lowered = detail.lower()
    if "customer self upgrade" in lowered or "service upgrade" in lowered:
        return ""
    detail = re.sub(
        r"^(?:Gen\s+[45]\s+)?(?:M\.2(?:\s+\d{4})?\s+SSD|[23]\.5\"\s+(?:SATA\s+)?HDD|SATA\s+HDD|SATA\s+SSD)\s+",
        "",
        detail,
        flags=re.I,
    )
    detail = re.sub(r"^up to\s+\d+,\s+up to\s+", "up to ", detail, flags=re.I)
    detail = re.sub(r",\s*for\b.*$", "", detail, flags=re.I)
    detail = strip_each_capacity_clauses(detail)
    detail = normalize_storage_phrase(detail)
    if not detail.lower().startswith("up to"):
        return ""
    return capacity_total_suffix(detail)


def compact_detail(detail: str) -> str:
    detail = normalize_storage_phrase(detail)
    if should_drop_max_line(detail):
        return ""
    detail = re.sub(r"\bup to\s+\d+,\s+up to\b", "up to", detail, flags=re.I)
    detail = re.sub(r",\s*for\b.*$", "", detail, flags=re.I)
    detail = strip_each_capacity_clauses(detail)
    return normalize_storage_phrase(format_capacity_total_phrase(detail))


def needs_bay_suffix(part: str, candidates: list[int], details: list[str]) -> bool:
    if "bay" in part.lower() or "open" in part.lower():
        return False
    return any("customer self upgrade" in details[index].lower() for index in candidates)


def ensure_bay_part(part: str) -> str:
    if re.search(r"\bHDD\s+bay\b", part, flags=re.I):
        return part
    match = re.match(r"^(1x)\s+((?:2\.5|3\.5)\"\s+HDD)$", part, flags=re.I)
    if match:
        return f"{match.group(1)} open {match.group(2)} bay"
    return re.sub(r"\bHDD\b", "HDD bay", part, count=1, flags=re.I)


def attach_single_drive_detail(base: str, details: list[str]) -> str:
    if not details:
        return base
    candidates = [detail for detail in details if "up to" in detail.lower()]
    if not candidates:
        return base
    prefix, combo = split_summary_prefix(base)
    parts = re.split(r"\s+\+\s+", combo)
    if len(parts) == 1:
        part = normalize_drive_part(parts[0])
        matching_details = [detail for detail in candidates if matching_detail_indexes(part, [detail])]
        multi_suffix = same_type_capacity_suffix(part, matching_details)
        if multi_suffix:
            return f"{prefix}: {part}, {multi_suffix}" if prefix else f"{part}, {multi_suffix}"
    suffixes = [capacity_suffix(detail) for detail in candidates]
    suffixes = [suffix for suffix in suffixes if suffix]
    if len({suffix.lower() for suffix in suffixes}) == 1 and suffixes:
        if suffixes[0].lower() not in base.lower():
            return f"{base}, {suffixes[0]}"
    return f"{base}; {'; '.join(unique_preserve(compact_detail(detail) for detail in candidates if compact_detail(detail)))}"


def lower_first(value: str) -> str:
    if value.startswith("Up to"):
        return "up to" + value[len("Up to") :]
    if value.startswith("One drive"):
        return "one drive" + value[len("One drive") :]
    if value.startswith("Two drives"):
        return "two drives" + value[len("Two drives") :]
    return value[:1].lower() + value[1:] if value else value


def finalize_storage_body(value: str) -> str:
    value = normalize_storage_phrase(value)
    value = strip_each_capacity_clauses(value)
    value = re.sub(r"\bup to\s+up to\b", "up to", value, flags=re.I)
    value = format_storage_output_body(value)
    value = strip_m2_size_tokens(value)
    value = re.sub(r"\s*;\s*", "; ", value)
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"\s+\+\s+", " + ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,.;")
    return value


def render_thinkstation_max_storage_direct(max_lines: list[str]) -> RenderedStorage:
    lines = [
        line
        for line in normalize_storage_tokens(max_lines)
        if not should_drop_max_line(line)
    ]
    if not lines:
        return RenderedStorage("", (), "Max Storage Support not found")
    return RenderedStorage(finalize_direct_storage_body("; ".join(lines)))


def render_raid_lines(raid_lines: list[str]) -> str:
    rendered: list[str] = []
    for line in normalize_storage_tokens(raid_lines):
        if "no support" in line.lower() or line.lower() == "none":
            continue
        if "raid" not in line.lower():
            continue
        line = re.sub(r"\bNone\b", "", line, flags=re.I)
        line = finalize_storage_body(line)
        if line:
            rendered.append(line)
    return "; ".join(unique_preserve(rendered))


def normalize_raid_sequence(sequence: str) -> str:
    values = [item for item in sequence.split("/") if item]
    order = {"0": 0, "1": 1, "5": 2, "6": 3, "10": 4}
    unique_values = unique_preserve(values)
    unique_values.sort(key=lambda item: order.get(item, 99))
    return "/".join(unique_values)


def render_controller_raid(controller_lines: list[str]) -> str:
    raids: list[str] = []
    for line in normalize_storage_tokens(controller_lines):
        if label_key(line) == "storage controller type interface raid cache":
            continue
        for match in re.finditer(r"\bRAID\s+([0-9/]+)\b", line, flags=re.I):
            raids.append(f"RAID {normalize_raid_sequence(match.group(1))}")
        if "raid" not in line.lower():
            for match in re.finditer(r"\b(0/1(?:/(?:5|6|10))*|0/1/10/5|0/1/5/10)\b", line):
                raids.append(f"RAID {normalize_raid_sequence(match.group(1))}")
    raids = unique_preserve(raids)
    if not raids:
        return ""
    rendered = [raids[0], *(raid.replace("RAID ", "", 1) for raid in raids[1:])]
    return f"RAID support via storage controllers: {', '.join(rendered)}"


def combine_raid_texts(*raid_texts: str) -> str:
    values: list[str] = []
    for raid_text in raid_texts:
        for value in re.split(r"\s*;\s*", raid_text or ""):
            value = finalize_storage_body(value)
            if value and "no support" not in value.lower():
                values.append(value)
    return "; ".join(unique_preserve(values))


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = normalize_storage_phrase(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def build_storage_short_spec(
    product_name: str,
    marketing_name: str,
    product_line: str,
    spec_text: str,
) -> StorageShortSpecResult:
    section = extract_storage_section(spec_text)
    if not section:
        status = "Skipped monitor" if is_monitor_product(product_name, marketing_name, spec_text) else "Storage not found"
        return StorageShortSpecResult(product_name, marketing_name, product_line, "", "", "", status, "")

    max_lines = collect_field(section, MAX_STORAGE_KEYS)
    if not max_lines:
        return StorageShortSpecResult(
            product_name,
            marketing_name,
            product_line,
            "",
            "",
            "",
            "Max Storage Support not found",
            "\n".join(section),
        )

    if product_line == "thinkstation":
        rendered = render_thinkstation_max_storage_direct(max_lines)
        short_spec = rendered.body if rendered.status == "OK" else ""
        explicit_raid = render_raid_lines(collect_field(section, RAID_KEYS))
        if short_spec and explicit_raid:
            short_spec = finalize_storage_body(f"{short_spec}; {explicit_raid}")
        return StorageShortSpecResult(
            product_name=product_name,
            marketing_name=marketing_name,
            product_line=product_line,
            storage_short_spec=short_spec,
            source_max_storage_support="\n".join(max_lines),
            source_raid="\n".join(collect_field(section, RAID_KEYS)),
            status=rendered.status,
            source_storage_section="\n".join(section),
        )

    rendered = render_max_storage(max_lines)
    explicit_raid = render_raid_lines(collect_field(section, RAID_KEYS))
    controller_raid = render_controller_raid(collect_storage_controllers(section))
    max_raid = render_raid_lines(list(rendered.raid_lines))
    raid_text = combine_raid_texts(explicit_raid, controller_raid, max_raid)

    status = rendered.status
    short_spec = ""
    if rendered.body and status == "OK":
        short_spec = rendered.body
        if raid_text:
            short_spec = f"{short_spec}; {raid_text}"
        short_spec = finalize_storage_body(short_spec)
    elif status == "OK":
        status = "Ambiguous storage rules"

    return StorageShortSpecResult(
        product_name=product_name,
        marketing_name=marketing_name,
        product_line=product_line,
        storage_short_spec=short_spec,
        source_max_storage_support="\n".join(max_lines),
        source_raid="\n".join(unique_preserve([*collect_field(section, RAID_KEYS), *collect_storage_controllers(section), *rendered.raid_lines])),
        status=status,
        source_storage_section="\n".join(section),
    )


def result_to_text(result: StorageShortSpecResult) -> str:
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)


def storage_feature_rows(result: StorageShortSpecResult) -> list[list[str]]:
    rows = [["L1 Feature", "L2 Feature", "Short Spec"]]
    if result.status == "OK" and result.storage_short_spec:
        rows.append(["PERFORMANCE", "Storage", result.storage_short_spec])
    else:
        rows.append(["ERROR", "Details", result.status])
    return rows


def write_storage_xlsx(workbook_path: Path, results: list[StorageShortSpecResult], workbook_layout: str) -> None:
    sheets: list[tuple[str, str | list[list[str]]]] = [
        (result.marketing_name, storage_feature_rows(result))
        for result in results
    ]
    write_xlsx(workbook_path, sheets, workbook_layout=workbook_layout)


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pypdf is not installed and no cached Storage text was available.") from exc

    reader = PdfReader(str(path))
    return join_pdf_page_texts(page.extract_text() or "" for page in reader.pages)


def load_storage_product_specs(paths: list[Path], runtime_text_dir: Path) -> list[ProductSpec]:
    pdf_paths = [path for path in paths if path.suffix.lower() == ".pdf"]
    cached_texts: dict[Path, str] = {}
    missing_pdf_paths: list[Path] = []

    for path in pdf_paths:
        cache_path = runtime_text_dir / f"{path.name}.txt"
        if cache_path.exists():
            cached_texts[path.resolve()] = normalize_text(cache_path.read_text(encoding="utf-8-sig"))
        else:
            missing_pdf_paths.append(path)

    extracted_texts: dict[Path, str] = {}
    if missing_pdf_paths:
        try:
            for path in missing_pdf_paths:
                extracted_texts[path.resolve()] = read_pdf_text(path)
                runtime_text_dir.mkdir(parents=True, exist_ok=True)
                (runtime_text_dir / f"{path.name}.txt").write_text(extracted_texts[path.resolve()], encoding="utf-8")
        except RuntimeError:
            manifest_path = runtime_text_dir.parent / "runtime_spec_text_storage_manifest.json"
            extracted_texts = extract_pdf_texts(missing_pdf_paths, runtime_text_dir, manifest_path)

    products: list[ProductSpec] = []
    for path in paths:
        if path.suffix.lower() == ".pdf":
            spec_text = cached_texts.get(path.resolve()) or extracted_texts[path.resolve()]
        else:
            spec_text = normalize_text(path.read_text(encoding="utf-8-sig"))
        products.append(
            ProductSpec(
                product=derive_product_name(path),
                display_name=derive_display_name(path),
                source_path=path,
                spec_text=spec_text,
            )
        )
    return products


def write_manifest(
    results: list[StorageShortSpecResult],
    workbook_path: Path,
    workbook_layout: str,
    config: StorageToolConfig,
) -> None:
    workbook_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "workbook": str(workbook_path),
                "generator": config.generator_name,
                "product_line": config.product_line,
                "workbook_layout": workbook_layout,
                "results": [asdict(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_args(config: StorageToolConfig) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Generate Storage-only Lenovo short specs for {config.product_line} spec files."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--spec-files", "--spec-pdfs", dest="spec_pdfs", nargs="+")
    source_group.add_argument("--spec-dir")
    parser.add_argument("--glob", default="*_Spec.PDF")
    parser.add_argument("--output-xlsx", default=config.output_xlsx)
    parser.add_argument(
        "--workbook-layout",
        choices=["per_product", "single_sheet_summary"],
        default="single_sheet_summary",
    )
    parser.add_argument("--runtime-text-dir", default=config.runtime_text_dir)
    parser.add_argument("--generated-text-dir", default=config.generated_text_dir)
    return parser.parse_args()


def run(config: StorageToolConfig) -> None:
    args = parse_args(config)
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    runtime_text_dir = Path(args.runtime_text_dir).resolve()
    generated_text_dir = Path(args.generated_text_dir).resolve()
    workbook_path = Path(args.output_xlsx).resolve()

    products = load_storage_product_specs(spec_paths, runtime_text_dir)
    storage_results: list[StorageShortSpecResult] = []
    generation_results: list[GenerationResult] = []

    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.source_path}")
        try:
            result = build_storage_short_spec(
                product_name=product.product,
                marketing_name=product.display_name,
                product_line=config.product_line,
                spec_text=product.spec_text,
            )
        except Exception as exc:
            result = StorageShortSpecResult(
                product_name=product.product,
                marketing_name=product.display_name,
                product_line=config.product_line,
                storage_short_spec="",
                source_max_storage_support="",
                source_raid="",
                status="Ambiguous storage rules",
                source_storage_section=f"{type(exc).__name__}: {exc}",
            )
        storage_results.append(result)
        generation_results.append(
            GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode=config.generator_name,
                shortdesc_text=result_to_text(result),
                usage=None,
                response_id=None,
            )
        )

    save_generation_texts(generation_results, generated_text_dir)
    write_storage_xlsx(workbook_path, storage_results, args.workbook_layout)
    write_manifest(storage_results, workbook_path, args.workbook_layout, config)

    status_counts: dict[str, int] = {}
    for result in storage_results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

    print(f"WORKBOOK\t{workbook_path}")
    print(f"SHEETS\t{1 if args.workbook_layout == 'single_sheet_summary' else len(storage_results)}")
    for status, count in sorted(status_counts.items()):
        print(f"STATUS\t{status}\t{count}")
