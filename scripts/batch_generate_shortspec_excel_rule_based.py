from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from batch_generate_shortspec_excel import (
    GenerationResult,
    collect_spec_paths,
    load_product_specs,
    save_generation_texts,
    write_xlsx,
)


TOP_LEVEL_SECTIONS = [
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "SECURITY & PRIVACY",
    "MANAGEABILITY",
    "ENVIRONMENTAL",
    "CERTIFICATIONS",
]

GENERIC_NOISE_LINES = {
    "/",
    "Notes:",
    "Notes",
    "Models",
    "Weight",
    "Display**",
    "Green Certifications",
    "Other Certifications",
    "Mil-Spec Test",
}

DISPLAY_NOISE_LINES = {
    "Display**",
    "Size",
    "Resolution",
    "Touch",
    "Type",
    "Brightness",
    "Surface",
    "Aspect Ratio",
    "Contrast Ratio",
    "Color",
    "Gamut",
    "Refresh Rate",
    "Viewing",
    "Angle",
    "Viewing Angle",
    "Viewing Angle (L/R/U/D)",
    "Key Features",
    "(L/R/U/D)",
}


def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\x07", "")
    text = text.replace("\x0c", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def clean_line(line: str) -> str:
    line = normalize_text(line)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"[®™©]", "", line)
    line = line.replace("USB-C®", "USB-C")
    line = line.replace("Wi-Fi®", "Wi-Fi")
    line = line.replace("Bluetooth®", "Bluetooth")
    line = line.replace("Lenovo®", "Lenovo")
    line = line.replace("ThinkPad®", "ThinkPad")
    line = line.replace("Windows®", "Windows")
    line = line.replace("Intel®", "Intel")
    line = line.replace("AMD Ryzen™", "AMD Ryzen")
    line = line.replace("AMD Radeon™", "AMD Radeon")
    line = line.replace("Qualcomm®", "Qualcomm")
    line = line.replace("Adreno™", "Adreno")
    line = line.replace("Hexagon™", "Hexagon")
    line = line.replace("Dolby Audio™", "Dolby Audio")
    line = line.replace("Dolby Voice®", "Dolby Voice")
    line = line.replace("Dolby Vision®", "Dolby Vision")
    line = line.replace("True Black ™", "True Black")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def split_lines(text: str) -> list[str]:
    return [clean_line(line) for line in normalize_text(text).split("\n") if clean_line(line)]


def is_section_heading(line: str) -> bool:
    normalized = line.upper()
    return normalized in TOP_LEVEL_SECTIONS or normalized in {"MIL-STD-810H", "MIL-STD-810G"}


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        upper = line.upper()
        if upper in TOP_LEVEL_SECTIONS or upper in {"MIL-STD-810H", "MIL-STD-810G"}:
            current = upper
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def normalize_label_token(line: str) -> str:
    return re.sub(r"\*+$", "", line).strip().lower()


def is_noise_line(line: str) -> bool:
    lowered = line.lower().strip()
    if line in GENERIC_NOISE_LINES:
        return True
    if lowered.startswith("feature with "):
        return True
    if lowered.startswith("please refer"):
        return True
    if lowered.startswith("lenovo reserves the right"):
        return True
    return False


def find_exact_index(lines: list[str], labels: Iterable[str]) -> int | None:
    normalized_labels = {normalize_label_token(label) for label in labels}
    for index, line in enumerate(lines):
        if normalize_label_token(line) in normalized_labels:
            return index
    return None


def slice_after_exact_label(lines: list[str], labels: Iterable[str], stop_labels: Iterable[str]) -> list[str]:
    start = find_exact_index(lines, labels)
    if start is None:
        return []

    stops = [normalize_label_token(label) for label in stop_labels]
    captured: list[str] = []
    for line in lines[start + 1 :]:
        lowered = normalize_label_token(line)
        if any(lowered == stop or lowered.startswith(stop + " ") for stop in stops):
            break
        captured.append(line)
    return captured


def find_index(lines: list[str], labels: Iterable[str]) -> int | None:
    normalized_labels = [label.lower() for label in labels]
    for index, line in enumerate(lines):
        lowered = line.lower()
        for label in normalized_labels:
            if lowered == label or lowered.startswith(label + " "):
                return index
    return None


def slice_after_label(lines: list[str], labels: Iterable[str], stop_labels: Iterable[str]) -> list[str]:
    start = find_index(lines, labels)
    if start is None:
        return []
    stops = [label.lower() for label in stop_labels]
    captured: list[str] = []
    for line in lines[start + 1 :]:
        lowered = line.lower()
        if any(lowered == stop or lowered.startswith(stop + " ") for stop in stops):
            break
        captured.append(line)
    return captured


def unique_preserve(lines: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def strip_footnote_markers(text: str) -> str:
    return re.sub(r"\[[0-9,\s]+\]", "", text).strip()


def split_bullet_fragments(lines: Iterable[str]) -> list[str]:
    fragments: list[str] = []
    for line in lines:
        parts = re.split(r"\s*•\s*", line)
        for part in parts:
            cleaned = strip_footnote_markers(clean_line(part))
            if cleaned:
                fragments.append(cleaned)
    return fragments


def split_condition_value(line: str) -> tuple[str, str] | None:
    match = re.match(r"^(?P<label>[^:]{1,120}):\s*(?P<value>.*)$", strip_footnote_markers(line))
    if not match:
        return None
    label = clean_line(match.group("label")).strip(" :-")
    value = clean_line(match.group("value"))
    if not label:
        return None
    return label, value


def is_platform_condition_label(label: str) -> bool:
    lowered = label.lower()
    return any(
        token in lowered
        for token in (
            "raptor lake",
            "meteor lake",
            "arrow lake",
            "lunar lake",
            "with u series",
            "with h series",
            "with intel",
            "with amd",
        )
    )


def normalize_platform_label(label: str) -> str:
    label = strip_footnote_markers(clean_line(label))
    label = re.sub(r"\bwith [^,:;]+? processors?\b", "", label, flags=re.I)
    label = re.sub(r"\bwith [^,:;]+? processor\b", "", label, flags=re.I)
    label = re.sub(r"\s+", " ", label).strip(" ,")
    return label


def split_platform_tokens(label: str) -> list[str]:
    normalized = normalize_platform_label(label)
    normalized = normalized.replace(" and ", ", ")
    parts = [part.strip(" ,") for part in normalized.split(",") if part.strip(" ,")]
    return unique_preserve(parts)


def join_platform_tokens(tokens: list[str]) -> str:
    tokens = unique_preserve([token.strip() for token in tokens if token.strip()])
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0]
    if len(tokens) == 2:
        return f"{tokens[0]} and {tokens[1]}"
    return f"{', '.join(tokens[:-1])} and {tokens[-1]}"


def format_or_list(items: list[str]) -> str:
    items = unique_preserve([item.strip() for item in items if item.strip()])
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} or {items[1]}"
    return f"{', '.join(items[:-1])} or {items[-1]}"


def normalize_memory_type_phrase(line: str) -> str:
    value = strip_footnote_markers(clean_line(line))
    value = value.replace("MoP (Memory on Package) memory", "MoP memory")
    value = value.replace(", MoP memory", " MoP memory")
    value = value.replace(", memory", " memory")
    value = re.sub(r"\s+", " ", value).strip(" ,")
    return value


def normalize_memory_slot_phrase(line: str) -> str:
    lowered = line.lower()
    if "csodimm" in lowered:
        return "2x CSODIMM"
    if "sodimm" in lowered:
        return "2x SODIMM"
    if "camm" in lowered:
        return "CAMM"
    return ""


def normalize_memory_value_line(line: str) -> str:
    value = strip_footnote_markers(clean_line(line))
    value = value.replace("MoP (Memory on Package) memory", "MoP memory")
    value = value.replace(", MoP memory", " MoP memory")
    value = re.sub(r"\s+", " ", value).strip(" ,")
    return value


def normalize_storage_value_line(line: str) -> str:
    value = strip_footnote_markers(clean_line(line))
    value = re.sub(r"^\*\s*", "", value)
    value = re.sub(r"^up to\b", "Up to", value, flags=re.I)
    value = re.sub(r"^one drive\b", "One drive", value, flags=re.I)
    return value.strip(" ,")


def parse_models_led_table(lines: list[str], headers: list[str]) -> list[str]:
    normalized_headers = [normalize_label_token(header) for header in headers]
    normalized_lines = [normalize_label_token(line) for line in lines]
    if normalized_lines[: len(normalized_headers)] != normalized_headers:
        return []

    data = [
        line
        for line in lines[len(headers) :]
        if not is_noise_line(line)
        and not normalize_label_token(line).startswith("feature with ")
        and not line.lower().startswith("the system ")
    ]
    column_count = len(headers)
    if column_count < 2 or len(data) < column_count:
        return []

    rendered: list[str] = []
    for index in range(0, len(data), column_count):
        row = data[index : index + column_count]
        if len(row) < column_count:
            break
        model_value = row[0]
        fragments = []
        for header, value in zip(headers[1:], row[1:]):
            if normalize_label_token(header) == "weight":
                fragments.append(value)
            else:
                fragments.append(f"{header}: {value}")
        rendered.append(f"{model_value}: {'; '.join(fragments)}")
    return unique_preserve(rendered)


def parse_models_led_multiline_table(lines: list[str], headers: list[str]) -> list[str]:
    normalized_headers = [normalize_label_token(header) for header in headers]
    normalized_lines = [normalize_label_token(line) for line in lines]
    if normalized_lines[: len(normalized_headers)] != normalized_headers:
        return []

    data = [
        line
        for line in lines[len(headers) :]
        if not is_noise_line(line)
        and not normalize_label_token(line).startswith("feature with ")
        and not line.lower().startswith("the system ")
    ]
    if len(headers) < 2 or not data:
        return []

    rendered: list[str] = []
    current_model: str | None = None
    current_values: list[str] = []

    def flush_current() -> None:
        nonlocal current_model, current_values
        if not current_model or not current_values:
            return
        value = re.sub(r"\s+", " ", " ".join(current_values)).strip()
        rendered.append(f"{current_model.rstrip(':')}: {value}")
        current_values = []

    for line in data:
        lowered = normalize_label_token(line)
        is_model_label = "model" in lowered and not any(
            token in lowered for token in ["mm", "inches", "kg", "lbs", "starting at", "supports up to"]
        )
        if is_model_label:
            flush_current()
            current_model = line.strip()
            continue

        if re.search(r"\d", line):
            if current_model is None:
                continue
            current_values.append(line)
            continue

        flush_current()
        current_model = line.strip()

    flush_current()
    return unique_preserve(rendered)


def extract_size_fragments(lines: list[str]) -> list[str]:
    pattern = re.compile(r"\d+(?:\.\d+)?\s*x\s*\d+(?:\.\d+)?\s*mm\s*\([^)]+\)", re.IGNORECASE)
    sizes: list[str] = []
    for line in lines:
        sizes.extend(re.sub(r"\s+", " ", match).strip() for match in pattern.findall(line))
    return unique_preserve(sizes)


def compact_or_join(items: list[str], sep: str = " ") -> list[str]:
    items = [item for item in items if item]
    if not items:
        return []
    return [sep.join(items)]


def normalize_port_line(line: str) -> str:
    line = line.replace("Thunderbolt 4 / USB4 40Gbps", "Thunderbolt 4 / USB4 40Gbps")
    line = line.replace("DisplayPort 2.1", "DP 2.1")
    line = line.replace("DisplayPort 1.4", "DP 1.4")
    line = line.replace(" and DP 2.1", " & DP 2.1")
    line = line.replace(" and DP 1.4", " & DP 1.4")
    line = line.replace(" and DisplayPort 1.4a", " and DisplayPort 1.4a")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def sanitize_generation_text(text: str) -> str:
    text = text.replace(" \n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def compact_windows_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []

    if any(token in line.lower() for line in lines for token in [" 64", "dg windows", "single language"]):
        keep = [
            line
            for line in lines
            if "single language" not in line.lower()
            and not (line.lower() == "linux" and any("ubuntu" in item.lower() or "fedora" in item.lower() for item in lines))
        ]
        return unique_preserve(keep)

    keep: list[str] = []
    has_win11_pro = any("windows 11 pro" == line.lower() for line in lines)
    has_win11_home = any("windows 11 home" == line.lower() for line in lines)
    if has_win11_pro and has_win11_home:
        keep.append("Windows 11 Pro or Home")
    else:
        keep.extend([line for line in lines if line.lower() in {"windows 11 pro", "windows 11 home"}])

    linux_lines = [line for line in lines if "ubuntu" in line.lower() or "fedora" in line.lower()]
    if linux_lines:
        if len(linux_lines) >= 2:
            keep.append("Fedora or Ubuntu Linux")
        else:
            keep.extend(linux_lines)

    others = [
        line
        for line in lines
        if line not in keep
        and not {"windows 11 pro", "windows 11 home"}.__contains__(line.lower())
        and "ubuntu" not in line.lower()
        and "fedora" not in line.lower()
        and "no preload" not in line.lower()
    ]
    keep.extend(others)
    return unique_preserve(keep)


def normalize_processor_summary(line: str) -> str:
    line = re.sub(r"\bProcessor\s+Processor(?:\*+(?:\[\d+\])?)?$", "Processor", line, flags=re.I)
    line = re.sub(r"[,;.]?\s*supports up to .*$", "", line, flags=re.I)
    line = re.sub(r"[,;.]?\s*up to \d+(?:\.\d+)?\s*ghz.*$", "", line, flags=re.I)
    line = re.sub(r"\s*Processor(?:\*+(?:\[\d+\])?)?$", " Processor", line, flags=re.I)
    line = re.sub(r"\s+", " ", line).strip(" ,;.")
    if line.lower().startswith("up to ") and line.endswith(" Processor"):
        line += "s"
    return line.strip()


def extract_processor(perf: list[str]) -> list[str]:
    stop_labels = [
        "Processor**",
        "AI (Artificial Intelligence)",
        "Operating System",
        "Operating System**",
        "Graphics",
        "Chipset",
        "Memory",
    ]
    block = slice_after_exact_label(perf, ["Processor Family"], stop_labels)
    if not block:
        block = slice_after_exact_label(perf, ["Processor"], stop_labels)

    lines = []
    for line in block:
        lowered = line.lower()
        if is_noise_line(line):
            continue
        if normalize_label_token(line) in {
            "processor family",
            "processor",
            "processor name",
            "cores",
            "threads",
            "base frequency",
            "max frequency",
            "cache",
            "processor graphics",
            "npu",
            "overall tops",
            "memory support",
        }:
            continue
        if "processor" not in lowered:
            continue
        normalized = normalize_processor_summary(line)
        if normalized and "processor" in normalized.lower():
            lines.append(normalized)
    return unique_preserve(lines[:2])


def extract_ai_category(perf: list[str]) -> list[str]:
    lines = slice_after_label(perf, ["AI PC Category"], ["NPU", "Operating System", "Graphics", "Memory"])
    out: list[str] = []
    for line in lines:
        lowered = line.lower()
        if is_noise_line(line):
            continue
        if normalize_label_token(line) in {"ai pc category"}:
            continue
        if any(token in lowered for token in ["copilot", "ai-ready", "ai pc", "workstation"]):
            out.append(line)
    return unique_preserve(out)


def tops_score(line: str) -> float | None:
    matches = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*TOPS\b", line, flags=re.I)]
    return max(matches) if matches else None


def strip_parenthetical_content(line: str) -> str:
    line = re.sub(r"\s*\([^)]*\)", "", line)
    return re.sub(r"\s+", " ", line).strip(" ,;.")


def extract_npu(perf: list[str]) -> list[str]:
    candidates: list[str] = []
    ai_lines = slice_after_exact_label(
        perf,
        ["AI (Artificial Intelligence)"],
        ["Operating System", "Operating System**", "Graphics", "Memory", "Storage"],
    )
    npu_start = find_exact_index(ai_lines, ["NPU", "NPU**"])
    if npu_start is not None:
        for line in ai_lines[npu_start + 1 :]:
            lowered = line.lower()
            if is_noise_line(line):
                continue
            if normalize_label_token(line) in {"npu", "tops", "overall tops", "ai pc category"}:
                continue
            if "tops" not in lowered and "npu" not in lowered:
                continue
            candidates.append(line)

    if not candidates:
        lines = slice_after_exact_label(
            perf,
            ["NPU", "NPU**"],
            ["Operating System", "Operating System**", "Graphics", "Memory", "Storage"],
        )
        for line in lines:
            lowered = line.lower()
            if is_noise_line(line):
                continue
            if normalize_label_token(line) in {"npu", "tops", "overall tops", "ai pc category"}:
                continue
            if "tops" not in lowered and "npu" not in lowered:
                continue
            candidates.append(line)

    scored_candidates = [(tops_score(line), line) for line in candidates]
    scored_candidates = [(score, line) for score, line in scored_candidates if score is not None]
    if scored_candidates:
        _, best_line = max(scored_candidates, key=lambda item: (item[0], len(item[1])))
        cleaned = strip_parenthetical_content(best_line)
        return [cleaned] if cleaned else []

    for line in candidates:
        cleaned = strip_parenthetical_content(line)
        if cleaned:
            return [cleaned]
    return []


def extract_operating_system(perf: list[str]) -> list[str]:
    lines = slice_after_exact_label(perf, ["Operating System", "Operating System**"], ["Graphics", "Chipset", "Memory"])
    cleaned = []
    has_linux_distro = any("ubuntu" in line.lower() or "fedora" in line.lower() for line in lines)
    for line in lines:
        lowered = line.lower()
        if normalize_label_token(line) in {"operating system"} or is_noise_line(line):
            continue
        if "license can be requested" in lowered or "some features may not be supported" in lowered:
            continue
        if "no preload" in lowered or "no operating system" in lowered:
            continue
        if lowered == "linux" and has_linux_distro:
            continue
        if lowered.startswith("windows") or "ubuntu" in lowered or "fedora" in lowered or lowered == "linux":
            cleaned.append(line)
    return compact_windows_lines(unique_preserve(cleaned))


def extract_graphics(perf: list[str]) -> list[str]:
    lines = slice_after_exact_label(perf, ["Graphics", "Graphics**"], ["Monitor Support", "Chipset", "Max Memory", "Memory Slots"])
    keep = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        if is_noise_line(line):
            continue
        if normalize_label_token(line) in {"graphics", "type", "memory", "key features"}:
            continue
        if any(token in lowered for token in ["intel ", "amd ", "nvidia ", "qualcomm ", "snapdragon ", "arc ", "adreno "]):
            if any(token in lowered for token in ["shared", "directx", "type", "memory", "graphics graphics"]):
                continue
            next_lower = lines[index + 1].lower() if index + 1 < len(lines) else ""
            rendered = line
            if "integrated" in next_lower and "(integrated)" not in lowered:
                rendered = f"{line} (integrated)"
            keep.append(rendered)
    return unique_preserve(keep[:4])


def summarize_memory(perf: list[str]) -> list[str]:
    max_lines = slice_after_exact_label(perf, ["Max Memory", "Max Memory[1]"], ["Memory Slots", "Memory Type", "Storage"])
    slot_lines = slice_after_exact_label(perf, ["Memory Slots"], ["Memory Type", "Storage"])
    type_lines = slice_after_exact_label(perf, ["Memory Type"], ["Storage", "Removable Storage"])

    max_lines = [
        line
        for line in max_lines
        if "based on the test results" not in line.lower()
        and normalize_label_token(line) not in {"max memory", "memory slots", "memory type"}
        and not is_noise_line(line)
    ]
    slot_line = slot_lines[0] if slot_lines else ""
    type_line = type_lines[0] if type_lines else ""

    conditioned_max = [split_condition_value(line) for line in max_lines if split_condition_value(line)]
    conditioned_slots = [split_condition_value(line) for line in slot_lines if split_condition_value(line)]
    conditioned_types = [split_condition_value(line) for line in type_lines if split_condition_value(line)]
    has_platform_conditioned_memory = any(
        condition and is_platform_condition_label(condition[0])
        for condition in conditioned_max + conditioned_slots
    )

    if has_platform_conditioned_memory:
        socketed_groups: list[dict[str, object]] = []
        soldered_groups: list[dict[str, object]] = []

        def ensure_group(groups: list[dict[str, object]], platforms: list[str]) -> dict[str, object]:
            platform_set = set(platforms)
            for group in groups:
                existing = set(group["platforms"])  # type: ignore[arg-type]
                if existing & platform_set:
                    group["platforms"] = unique_preserve([*group["platforms"], *platforms])  # type: ignore[index]
                    return group
            group = {
                "platforms": unique_preserve(platforms),
                "capacities": [],
                "types": [],
                "slot": "",
            }
            groups.append(group)
            return group

        for label, value in conditioned_max:
            platforms = split_platform_tokens(label)
            if not platforms:
                continue
            lowered = value.lower()
            if "soldered memory" in lowered:
                group = ensure_group(soldered_groups, platforms)
                capacity_match = re.search(r"(\d+GB)", value, re.I)
                if capacity_match:
                    group["capacities"] = unique_preserve([*group["capacities"], capacity_match.group(1)])  # type: ignore[index]
                continue

            group = ensure_group(socketed_groups, platforms)
            capacity_match = re.search(r"(up to\s+\d+GB)", value, re.I)
            if capacity_match:
                capacity = capacity_match.group(1)
                capacity = capacity[0].upper() + capacity[1:]
                group["capacities"] = unique_preserve([*group["capacities"], capacity])  # type: ignore[index]
            type_match = re.search(r"\b(?:LPDDR\d+X?-\d+|DDR\d-\d+)\b", value, re.I)
            if type_match:
                group["types"] = unique_preserve([*group["types"], type_match.group(0).upper()])  # type: ignore[index]

        for label, value in conditioned_types:
            platforms = split_platform_tokens(label)
            if not platforms:
                continue
            normalized_type = normalize_memory_type_phrase(value)
            target_groups = soldered_groups if "mop" in normalized_type.lower() or "lpddr" in normalized_type.lower() else socketed_groups
            group = ensure_group(target_groups, platforms)
            group["types"] = unique_preserve([*group["types"], normalized_type])  # type: ignore[index]

        for label, value in conditioned_slots:
            platforms = split_platform_tokens(label)
            if not platforms:
                continue
            if "soldered" in value.lower() or "no slots" in value.lower():
                ensure_group(soldered_groups, platforms)
                continue
            slot_phrase = normalize_memory_slot_phrase(value)
            if not slot_phrase:
                continue
            group = ensure_group(socketed_groups, platforms)
            if not group["slot"]:
                group["slot"] = slot_phrase

        rendered: list[str] = []
        complex_multi_platform_socketed = any(len(group["platforms"]) > 1 for group in socketed_groups)  # type: ignore[arg-type]

        for group in socketed_groups:
            label = join_platform_tokens(group["platforms"])  # type: ignore[arg-type]
            capacities = group["capacities"]  # type: ignore[assignment]
            types = group["types"]  # type: ignore[assignment]
            slot = group["slot"]  # type: ignore[assignment]
            pieces: list[str] = []
            if capacities:
                pieces.append(format_or_list(capacities))
            if types:
                pieces.append(format_or_list(types))
            text = " ".join(piece for piece in pieces if piece).strip()
            if slot:
                text = f"{text}, {slot}" if text else slot
            if text:
                rendered.append(f"{label}: {text}")

        for group in soldered_groups:
            label = join_platform_tokens(group["platforms"])  # type: ignore[arg-type]
            capacities = group["capacities"]  # type: ignore[assignment]
            types = group["types"]  # type: ignore[assignment]
            type_text = normalize_memory_type_phrase(format_or_list(types)) if types else "memory"
            if complex_multi_platform_socketed:
                rendered.append(f"{label}:")
                for capacity in capacities:
                    rendered.append(f"{capacity} {type_text}, soldered")
            else:
                capacity_text = format_or_list(capacities)
                rendered.append(f"{label}: {capacity_text} {type_text}, soldered".strip())

        rendered = [re.sub(r"\s+", " ", line).strip() for line in rendered if line.strip()]
        if rendered:
            return unique_preserve(rendered)

    if max_lines and all(re.match(r"^\d+GB", line) for line in max_lines):
        out = []
        for line in max_lines:
            capacity = re.match(r"^(\d+GB)", line)
            if capacity:
                if "soldered" in slot_line.lower() or "soldered" in line.lower():
                    rendered = f"{capacity.group(1)} {type_line}, soldered".strip()
                else:
                    rendered = f"{capacity.group(1)} {type_line}".strip()
                out.append(re.sub(r"\s+", " ", rendered))
        return unique_preserve(out)

    if max_lines:
        first = max_lines[0]
        if slot_line:
            lowered = slot_line.lower()
            if "two" in lowered and "sodimm" in lowered:
                first = f"{first}, 2x SODIMM"
            elif "one" in lowered and ("so-dimm" in lowered or "sodimm" in lowered):
                first = f"{first}, 1x SO-DIMM"
            elif "1x so-dimm" in first.lower() or "1x soldered + 1x so-dimm" in first.lower():
                pass
            elif "soldered" in lowered and "no slots" in lowered and type_line and type_line.lower() not in first.lower():
                first = f"{first}, soldered"
        return [re.sub(r"\s+", " ", first).strip()]

    return []


def summarize_storage(perf: list[str]) -> list[str]:
    support = slice_after_exact_label(
        perf,
        ["Max Storage Support", "Max Storage Support[1]", "Storage Support"],
        ["Storage Slot", "Storage Type", "Removable Storage", "Multi-Media"],
    )
    slot = slice_after_exact_label(perf, ["Storage Slot", "Storage Slot[2]"], ["Storage Type", "Removable Storage", "Multi-Media"])
    storage_type = slice_after_exact_label(perf, ["Storage Type", "Storage Type**"], ["RAID", "Removable Storage", "Multi-Media"])

    support = [
        line
        for line in support
        if "based on the test results" not in line.lower()
        and normalize_label_token(line) not in {"storage support", "max storage support"}
        and not is_noise_line(line)
    ]
    slot_line = slot[0] if slot else ""
    slot_blob = " ".join(slot)
    type_blob = " ".join(storage_type)
    out: list[str] = []

    storage_fragments = split_bullet_fragments(support)
    has_platform_conditioned_storage = any(
        (fragment.endswith(":") and is_platform_condition_label(fragment[:-1]))
        or (
            split_condition_value(fragment)
            and is_platform_condition_label(split_condition_value(fragment)[0])  # type: ignore[index]
        )
        for fragment in storage_fragments
    )

    if has_platform_conditioned_storage:
        rendered: list[str] = []
        current_label = ""
        current_values: list[str] = []

        def flush_group() -> None:
            nonlocal current_label, current_values
            if not current_label:
                return
            rendered.append(f"{normalize_platform_label(current_label)}:")
            rendered.extend(unique_preserve([normalize_storage_value_line(value) for value in current_values if value.strip()]))
            current_label = ""
            current_values = []

        for fragment in storage_fragments:
            if fragment.endswith(":") and is_platform_condition_label(fragment[:-1]):
                flush_group()
                current_label = fragment[:-1]
                continue

            conditioned = split_condition_value(fragment)
            if conditioned and is_platform_condition_label(conditioned[0]):
                flush_group()
                current_label = conditioned[0]
                if conditioned[1]:
                    current_values.append(conditioned[1])
                continue

            current_values.append(fragment)

        flush_group()

        rendered = [line for line in rendered if line and line != ":"]
        if rendered:
            return unique_preserve(rendered)

    for line in support:
        if line.startswith("One drive, up to") and slot_line:
            slot_match = re.search(r"(M\.2 \d{4})", slot_line)
            size_match = re.search(r"up to ([0-9.]+TB)", line, re.I)
            if slot_match and size_match:
                entry = f"Up to 1x {size_match.group(1)} {slot_match.group(1)} PCIe NVMe SSD"
                out.append(entry)
                continue
        if line.startswith("Up to two drives") or line.startswith("Up to two M.2"):
            if "m.2" in line.lower() and "pcie" in f"{slot_blob} {type_blob}".lower():
                out.append("Up to two M.2 PCIe NVMe SSD")
            else:
                out.append(line)
            continue
        out.append(line)

    if "RAID 0/1 support" in perf and "RAID 0/1 support" not in out:
        out.append("RAID 0/1 support")

    if not out and type_blob:
        interfaces = [line for line in storage_type if "PCIe" in line or "SSD" in line]
        out.extend(interfaces)

    return unique_preserve(out)


def summarize_audio(perf: list[str]) -> list[str]:
    audio_chip = slice_after_label(perf, ["Audio Chip"], ["Speakers", "Microphone", "Camera", "Camera**", "Battery"])
    speakers = slice_after_label(perf, ["Speakers"], ["Microphone", "Camera", "Camera**", "Battery"])
    microphone = slice_after_label(perf, ["Microphone"], ["Camera", "Camera**", "Battery"])

    out: list[str] = []
    for line in audio_chip:
        if "high definition (hd) audio" in line.lower() or "soundwire" in line.lower():
            cleaned = line
            cleaned = re.sub(r", .+codec.*", "", cleaned, flags=re.I)
            out.append(cleaned)
            break

    for group in (speakers, microphone):
        for line in group:
            if line.lower().startswith("no "):
                continue
            if "stereo speakers" in line.lower() or "dolby" in line.lower() or "microphone" in line.lower():
                line = line.replace("optimized with ", "")
                out.append(line)
                if group is speakers:
                    break

    return unique_preserve(out)


def normalize_camera_line(line: str) -> str:
    line = line.replace("Front ", "Front ")
    line = line.replace("World Facing 5.0-megapixel", "rear 5.0MP")
    line = line.replace("World Facing", "rear")
    line = line.replace("5.0-megapixel", "5.0MP")
    line = line.replace(", fixed focus", "")
    line = line.replace(", autofocus", "")
    line = line.replace(", match-on-chip", "")
    line = line.replace(" ;", ";")
    line = re.sub(r"\s+", " ", line).strip()
    line = line.replace("rear rear", "rear")
    return line


def summarize_camera(perf: list[str]) -> tuple[str, list[str]]:
    camera_lines = slice_after_exact_label(perf, ["Camera", "Camera**"], ["Battery", "Battery**"])
    keep = []
    optional = False
    for line in camera_lines:
        lowered = line.lower()
        if is_noise_line(line):
            continue
        if lowered.startswith("no camera"):
            optional = True
            continue
        if any(token in lowered for token in ["720p", "1080p", "5.0mp", "ir", "privacy shutter", "rear"]):
            keep.append(normalize_camera_line(line))
    label = "Camera*" if optional else "Camera"
    return label, unique_preserve(keep)


def summarize_battery(perf: list[str]) -> list[str]:
    battery_lines = slice_after_label(perf, ["Battery", "Battery**"], ["Battery Life", "Power Adapter", "Power Adapter**"])
    battery_life = slice_after_label(
        perf,
        ["Battery Life", "Battery Life[2]", "Battery Life[3]", "Max Battery Life", "Max Battery Life[1]"],
        ["Power Adapter", "Power Adapter**"],
    )

    capacity_matches: list[str] = []
    for line in battery_lines:
        capacity_matches.extend(re.findall(r"\d+(?:\.\d+)?Wh", line))
    capacities = unique_preserve(capacity_matches)
    rapid = any("rapid charge" in line.lower() for line in battery_lines)

    hour_match = None
    for line in battery_lines + battery_life:
        match = re.search(r"up to (\d+(?:\.\d+)?) hr", line, re.I)
        if match:
            hour_match = match.group(1)
            break
        fallback_match = re.search(r"(\d+(?:\.\d+)?) hr", line, re.I)
        if fallback_match:
            hour_match = fallback_match.group(1)
            break

    if capacities:
        label = " or ".join(capacities)
        result = f"{label} battery"
        if hour_match:
            result += f", up to {hour_match} hr"
        if rapid:
            result += ", Rapid Charge"
        return [result]

    return unique_preserve([line for line in battery_lines if "battery" in line.lower()])


def normalize_power_adapter_line(line: str) -> str:
    line = re.sub(r"\([^)]*\)", "", line)
    line = line.replace("AC adapter", "adapter")
    line = line.replace(", supports PD 3.0, 100-240V, 50-60Hz", ", PD 3.0")
    line = line.replace(", supports PD 3.0", ", PD 3.0")
    line = line.replace(" nano GaN ", " nano GaN ")
    line = line.replace(" slim GaN ", " slim GaN ")
    line = line.replace(" slim ", " slim ")
    line = line.replace("  ", " ")
    line = line.replace("adapter adapter", "adapter")
    return line.strip(" ,")


def summarize_power_adapter(perf: list[str]) -> tuple[str, list[str]]:
    lines = slice_after_exact_label(perf, ["Power Adapter", "Power Adapter**"], ["DESIGN", "Display"])
    out: list[str] = []
    optional = False
    for line in lines:
        lowered = line.lower()
        if is_noise_line(line):
            continue
        if normalize_label_token(line) in {"power adapter"}:
            continue
        if lowered.startswith("no power adapter"):
            optional = True
            continue
        if "offerings depend on the country" in lowered:
            continue
        if "adapter" in lowered:
            normalized = normalize_power_adapter_line(line)
            normalized = normalized.replace("USB-C slim GaN adapter, PD 3.0", "USB-C slim GaN adapter, PD 3.0")
            normalized = normalized.replace("USB-C nano GaN adapter, PD 3.0", "USB-C nano GaN adapter, PD 3.0")
            normalized = normalized.replace("USB-C slim adapter, PD 3.0", "USB-C slim adapter, PD 3.0")
            normalized = normalized.replace("USB-C adapter, PD 3.0", "USB-C adapter, PD 3.0")
            out.append(normalized)
    label = "Power Adapter*" if optional or len(out) > 1 else "Power Adapter"
    return label, unique_preserve(out)


def render_display_offerings(design: list[str]) -> list[str]:
    display_block = slice_after_exact_label(
        design,
        ["Display", "Display**"],
        ["Touchscreen", "Touchscreen**", "Screen-to-Body Ratio", "Multi-mode", "Input Device"],
    )
    if not display_block:
        return []

    display_block = [
        line
        for line in display_block
        if line not in DISPLAY_NOISE_LINES and not is_noise_line(line)
    ]

    if any(re.fullmatch(r"\d+(?:\.\d+)?\"", line) for line in display_block):
        offerings: list[list[str]] = []
        current: list[str] = []
        for line in display_block:
            if re.fullmatch(r"\d+(?:\.\d+)?\"", line):
                if current:
                    offerings.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            offerings.append(current)

        rendered_entries: list[tuple[str, str]] = []
        for offering in offerings:
            header, value = render_display_table_entry(offering)
            if header:
                rendered_entries.append((header, value))
        return flatten_display_entries(rendered_entries)

    rendered_entries: list[tuple[str, str]] = []
    current_header = None
    current_values: list[str] = []
    for line in display_block:
        if re.search(r'^\d+(?:\.\d+)?".*\(\d+x\d+\)', line):
            if current_header:
                rendered_entries.append((current_header, ", ".join(unique_preserve(current_values))))
            current_header = line
            current_values = []
        else:
            current_values.append(line)
    if current_header:
        rendered_entries.append((current_header, ", ".join(unique_preserve(current_values))))
    return flatten_display_entries(rendered_entries)


def flatten_display_entries(entries: list[tuple[str, str]]) -> list[str]:
    merged: list[str] = []
    last_header = None
    collected_values: list[str] = []

    def flush() -> None:
        nonlocal collected_values, last_header
        if not last_header:
            return
        merged.append(last_header)
        merged.extend(unique_preserve([value for value in collected_values if value]))
        collected_values = []

    for header, value in entries:
        if header != last_header:
            flush()
            last_header = header
        if value:
            collected_values.append(value)
    flush()
    return merged


def render_display_table_entry(tokens: list[str]) -> tuple[str, str]:
    size = tokens[0]
    resolution_parts: list[str] = []
    panel = ""
    surface = ""
    aspect = ""
    touch = ""
    brightness = ""
    gamut = ""
    refresh = ""
    features: list[str] = []

    for token in tokens[1:]:
        lowered = token.lower()
        if not resolution_parts and ("(" in token or token in {"FHD", "WUXGA", "WQUXGA", "2.8K", "HD"}):
            resolution_parts.append(token)
            continue
        if resolution_parts and len(resolution_parts) < 2 and token.startswith("("):
            resolution_parts.append(token)
            continue
        if not touch and any(word in lowered for word in ["touch", "nontouch", "gmf", "ogm", "oncell", "addon"]):
            if "oncell" in lowered:
                touch = "on-cell touch"
            elif "addon" in lowered:
                touch = "Add-on Film Touch"
            else:
                touch = token
            continue
        if not panel and any(word in lowered for word in ["ips", "oled", "tn"]):
            panel = re.sub(r"\[[0-9]+\]", "", token)
            continue
        if not brightness and "nits" in lowered:
            brightness = token
            continue
        if not surface and any(word in lowered for word in ["anti-glare", "antiglare", "anti-reflection", "antireflection", "anti-smudge", "agaras", "agas", "aras"]):
            surface = token
            continue
        if not aspect and re.fullmatch(r"\d+:\d+", token):
            aspect = token
            continue
        if not gamut and any(word in lowered for word in ["% ntsc", "% srgb", "dci-p3"]):
            gamut = token
            continue
        if not refresh and "hz" in lowered:
            refresh = token
            continue
        if any(word in lowered for word in ["eyesafe", "privacy guard", "displayhdr", "dolby vision", "3m", "gorilla", "x-rite", "tüv", "tuv", "low power", "low blue light"]):
            features.append(token)

    header_parts = [size]
    if resolution_parts:
        header_parts.extend(resolution_parts)
    if panel:
        header_parts.append(panel)
    if surface.endswith("anti-"):
        surface = "Anti-glare"
    if surface:
        header_parts.append(surface)
    if aspect:
        header_parts.append(aspect)
    header = " ".join(part for part in header_parts if part)

    value_parts = [brightness, gamut]
    if touch and "nontouch" not in touch.lower():
        value_parts.append(touch)
    if refresh:
        value_parts.append(refresh)
    value_parts.extend(features[:4])
    value = ", ".join(part for part in value_parts if part)

    return header, value


def summarize_screen_to_body(design: list[str]) -> list[str]:
    lines = slice_after_exact_label(design, ["Screen-to-Body Ratio"], ["Multi-mode", "Input Device", "Pen", "Keyboard"])
    return lines[:1]


def summarize_multimode(design: list[str]) -> list[str]:
    lines = slice_after_exact_label(design, ["Multi-mode"], ["Input Device", "Pen", "Keyboard"])
    return [line for line in lines if "mode" in line.lower() or "hinge" in line.lower()][:1]


def summarize_pen(design: list[str]) -> list[str]:
    lines = slice_after_exact_label(design, ["Pen"], ["Keyboard", "Keyboard Backlight", "UltraNav", "Mechanical"])
    positive = [line for line in lines if not line.lower().startswith("no pen") and not line.lower().startswith("no support")]
    if not positive:
        return []
    if any("lenovo integrated pen" in line.lower() for line in positive):
        return ["Lenovo Integrated Pen*"]
    return [re.sub(r", .+", "", positive[0])]


def summarize_keyboard(design: list[str]) -> list[str]:
    keyboard = slice_after_exact_label(design, ["Keyboard"], ["Keyboard Backlight", "UltraNav", "Mechanical", "Touchpad"])
    backlight = slice_after_exact_label(design, ["Keyboard Backlight"], ["UltraNav", "Mechanical", "Touchpad"])
    if not keyboard:
        return []
    base = keyboard[0]
    parts: list[str] = []
    if "6-row" in base.lower():
        parts.append("6-row")
    if "spill-resistant" in base.lower():
        parts.append("spill-resistant")
    if "numeric keypad" in base.lower():
        parts.append("numeric keypad")
    if "air intake design" in base.lower():
        parts.append("air intake design")
    if "copilot key" in base.lower():
        parts.append("Copilot key")

    if backlight:
        lowered = " ".join(backlight).lower()
        if "led backlight" in lowered and "non-backlight" in lowered:
            parts.append("optional backlight")
        elif "led backlight" in lowered:
            parts.append("backlight")

    if not parts:
        parts.append(base)
    return [", ".join(parts)]


def summarize_touchpad(design: list[str]) -> list[str]:
    block = slice_after_exact_label(design, ["UltraNav", "UltraNav**", "Touchpad"], ["Mechanical", "Dimensions (WxDxH)", "Weight", "Case Color", "Color"])
    if not block:
        return []
    size_lines = extract_size_fragments(block)
    text_blob = " ".join(block).lower()
    label = ""

    if "models without nfc" in text_blob and "models with nfc" in text_blob and "mylar" in text_blob and "glass-like mylar" in text_blob:
        label = "TrackPoint, Mylar or glass-like Mylar surface TrackPad"
    elif "buttonless glass surface multi-touch trackpad" in text_blob and "buttonless glass surface multi-touch haptic touchpad" in text_blob:
        label = "Glass surface Trackpad or Haptic Touchpad"
    elif "3-button trackpoint" in text_blob and "glass-like mylar" in text_blob:
        label = "TrackPoint and glass-like Mylar surface TrackPad"
    elif "haptic touchpad" in text_blob and "trackpoint" not in text_blob:
        if "buttonless" in text_blob and "glass surface" in text_blob:
            label = "Buttonless glass surface multi-touch Haptic Touchpad"
        else:
            label = "Haptic Touchpad"
    elif "haptic touchpad" in text_blob:
        label = "TrackPoint and glass surface Haptic Touchpad"
    elif "glass-like mylar" in text_blob and "3-button trackpad" in text_blob:
        label = "TrackPoint and glass-like Mylar surface 3-button Trackpad"
    elif "glass-like mylar" in text_blob and "trackpad" in text_blob:
        label = "TrackPoint and glass-like Mylar surface TrackPad"
    elif "glass-like mylar" in text_blob:
        label = "TrackPoint and glass-like Mylar surface touchpad"
    elif "glass surface 3-button trackpad" in text_blob:
        label = "TrackPoint and glass surface 3-button Trackpad"
    elif "buttonless mylar" in text_blob and "trackpoint" not in text_blob:
        label = "Mylar surface touchpad"
    elif "glass-like mylar surface" in text_blob:
        label = "TrackPoint and glass-like Mylar surface 3-button Trackpad"
    elif "mylar surface" in text_blob:
        label = "TrackPoint and Mylar surface touchpad"

    out = [label] if label else []
    out.extend(size_lines[:2])
    return unique_preserve(out)


def summarize_dimensions(design: list[str]) -> list[str]:
    lines = slice_after_exact_label(design, ["Dimensions (WxDxH)", "Dimensions (WxDxH)[1]"], ["Weight", "Weight[2]", "Case Color", "Color", "Case Material"])
    models_table = parse_models_led_multiline_table(lines, ["Models", "Dimensions"])
    if models_table:
        return models_table[:6]
    return [line for line in lines if re.search(r"\d", line)]


def summarize_weight(design: list[str]) -> list[str]:
    lines = slice_after_exact_label(design, ["Weight", "Weight[2]"], ["Case Color", "Color", "Case Material"])
    models_table = parse_models_led_table(lines, ["Models", "Weight"])
    if models_table:
        return models_table[:6]
    filtered = [line for line in lines if "starting at" in line.lower() or "models with" in line.lower()]
    return filtered[:6]


def summarize_color(design: list[str]) -> list[str]:
    lines = slice_after_exact_label(design, ["Case Color"], ["Case Material"])
    if not lines:
        lines = slice_after_exact_label(design, ["Color"], ["Case Material"])
    filtered = [
        line
        for line in lines
        if not is_noise_line(line)
        and "models with" not in line.lower()
        and re.fullmatch(r"[A-Za-z][A-Za-z -]+", line)
    ]
    return unique_preserve(filtered[:4])


def summarize_case_material(design: list[str]) -> list[str]:
    lines = slice_after_exact_label(design, ["Case Material"], ["CONNECTIVITY", "Network", "WLAN + Bluetooth"])
    filtered: list[str] = []
    for line in lines:
        lowered = line.lower()
        if is_noise_line(line):
            continue
        if "please visit" in lowered or lowered.startswith("the system dimensions may vary") or lowered.startswith("the system weight is approximate"):
            continue
        if "•" in line:
            parts = [part.strip(" •") for part in line.split("•") if part.strip(" •")]
            filtered.extend(parts)
            continue
        filtered.append(line)
    return filtered[:4]


def summarize_ethernet(conn: list[str]) -> list[str]:
    lines = slice_after_exact_label(conn, ["Ethernet"], ["NFC", "Ports", "Docking"])
    for line in lines:
        lowered = line.lower()
        if "no onboard ethernet" in lowered:
            return []
        if "gigabit" in lowered:
            return ["Gigabit onboard Ethernet"]
    return []


def summarize_wlan(conn: list[str]) -> list[str]:
    lines = slice_after_exact_label(conn, ["WLAN + Bluetooth", "WLAN + Bluetooth[1]", "WLAN + Bluetooth**"], ["WWAN", "WWAN**", "SIM Card", "Ethernet", "NFC"])
    filtered = [line for line in lines if "subject to the regulatory requirements" not in line.lower()]
    return unique_preserve(filtered[:2])


def parse_wwan_marketed(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        lowered = line.lower()
        if lowered.startswith("no support") or "upgradable" in lowered or "kddi esim program" in lowered:
            continue
        if "5g sub-6 ghz" in lowered:
            out.append("5G Sub-6 GHz with embedded eSIM")
            continue
        cat_match = re.search(r"(4G LTE CAT\d+)", line, re.I)
        if cat_match:
            out.append(f"{cat_match.group(1).upper()} with embedded eSIM")
            continue
        if "embedded esim" in lowered:
            out.append(re.sub(r".*?([45]G.+embedded eSIM.*)", r"\1", line, flags=re.I))
    return unique_preserve(out)


def summarize_wwan(conn: list[str]) -> tuple[str, list[str]]:
    lines = slice_after_exact_label(conn, ["WWAN", "WWAN*", "WWAN**"], ["SIM Card", "Ethernet", "NFC", "Ports"])
    optional = any("no support" in line.lower() or "upgradable" in line.lower() for line in lines)
    marketed = parse_wwan_marketed(lines)
    label = "WWAN*" if optional or marketed else "WWAN"
    return label, marketed


def summarize_nfc(conn: list[str]) -> list[str]:
    lines = slice_after_label(conn, ["NFC", "NFC[3]"], ["Ports", "Docking"])
    if any("near field communication" in line.lower() for line in lines):
        return ["Near Field Communication*"] if any("no support" in line.lower() for line in lines) else ["Near Field Communication"]
    return []


def summarize_ports(conn: list[str]) -> list[str]:
    lines = slice_after_label(conn, ["Ports", "Ports[1]"], ["Docking"])
    out: list[str] = []
    optional_mode = False
    for line in lines:
        lowered = line.lower()
        normalized = normalize_label_token(line)
        if normalized in {"standard ports", "optional ports"}:
            optional_mode = normalized.startswith("optional")
            continue
        if "transfer speed of the ports" in lowered:
            continue
        if line.startswith("1x") or line.startswith("2x"):
            normalized = re.sub(r"\*+$", "", normalize_port_line(line)).rstrip()
            if optional_mode:
                normalized = f"{normalized}*"
            out.append(normalized)
    return unique_preserve(out)


def summarize_docking(conn: list[str]) -> list[str]:
    lines = slice_after_label(conn, ["Docking"], ["SECURITY & PRIVACY", "Security"])
    text_blob = " ".join(lines).lower()
    if "thunderbolt" in text_blob and "usb-c" in text_blob:
        return ["Docking support via Thunderbolt or USB-C"]
    if "usb-c" in text_blob:
        return ["Docking support via USB-C"]
    return []


def summarize_security(sec: list[str]) -> list[str]:
    out: list[str] = []
    if any("thinkshield" in line.lower() for line in sec):
        out.append("ThinkShield")

    for line in sec:
        lowered = line.lower()
        if "pluton" in lowered and "tpm" in lowered:
            out.append("Discrete TPM 2.0 and Microsoft Pluton TPM 2.0")
            break
        if "discrete tpm 2.0" in lowered:
            cleaned = "Discrete TPM 2.0"
            if "firmware tpm 2.0" in lowered:
                out.append(cleaned)
                out.append("Firmware TPM 2.0")
            else:
                out.append(cleaned)
            break

    for line in sec:
        lowered = line.lower()
        if "kensington" in lowered and "nano" in lowered:
            out.append("Kensington Nano Security Slot")
            break
        if "kensington security slot" in lowered:
            out.append("Kensington Security Slot")
            break

    for line in sec:
        lowered = line.lower()
        if "smart card reader" in lowered and "supports iso 7816 and emv" in lowered:
            out.append("Smart card reader, supports ISO 7816 and EMV*")
            break
    for line in sec:
        lowered = line.lower()
        if "fingerprint reader" in lowered and not lowered.startswith("no "):
            if "match-on-chip" in lowered:
                out.append("Touch style MOC fingerprint reader*")
            else:
                out.append("Touch style fingerprint reader*")
            break

    for line in sec:
        lowered = line.lower()
        if "camera privacy shutter" in lowered:
            out.append("Camera privacy shutter*")
            break

    for line in sec:
        lowered = line.lower()
        if "windows hello" in lowered:
            out.append("IR camera for Windows Hello (facial recognition)*")
            break

    for line in sec:
        lowered = line.lower()
        if "privacy guard with privacy alert" in lowered:
            if "software solution" in lowered:
                out.append("Privacy Guard with Privacy Alert (software solution)")
            else:
                out.append("Privacy Guard with Privacy Alert*")
            break

    for line in sec:
        lowered = line.lower()
        if "human presence detection" in lowered:
            if "ultrasonic" in lowered:
                out.append("Ultrasonic Human Presence Detection*")
            elif "computer vision" in lowered:
                out.append("Computer Vision-based Human Presence Detection*")
            else:
                out.append("Human Presence Detection*")

    return unique_preserve(out)


def normalize_manageability_value(line: str) -> str:
    value = clean_line(line)
    value = re.sub(r"^System Management\*?\*?\s*", "", value, flags=re.I).strip()
    value = value.strip("/ ").strip()
    if not value:
        return ""

    lowered = value.lower()
    if lowered.startswith("non"):
        return ""
    if lowered in {"notes:", "notes", "/", "*", "*[1]", "***[1]", "[1]"}:
        return ""
    if lowered.startswith(("service", "warranty", "base warranty", "accessories", "bundled accessories")):
        return ""
    if lowered.startswith(("operating requirements", "operating environment", "altitude", "temperature", "relative humidity")):
        return ""
    if lowered.startswith(("storage", "operating:", "storage:", "maximum altitude")):
        return ""
    if lowered.startswith(("for more compatible accessory", "more information of warranty policy", "the warranty upgrades may")):
        return ""
    if "http://" in lowered or "https://" in lowered:
        return ""
    if lowered.startswith(("lenovo ", "thinkpad ")):
        return ""
    if any(
        token in lowered
        for token in (
            "platform require",
            "platform requires",
            "eligible intel processor",
            "manageability use cases",
            "firmware enhancements",
            "offers a superset of dash",
            "defined capabilities",
            "see intel vpro platform",
            "all versions of the intel vpro",
            "technology support",
        )
    ):
        return ""
    if "vpro" not in lowered and "dash" not in lowered and "manageability" not in lowered:
        return ""

    value = re.sub(r"\s+", " ", value).strip()
    if value.lower() == "amd pro manageability":
        return "AMD PRO Manageability"
    if value.lower() == "amd pro manageability*":
        return "AMD PRO Manageability*"
    return value


def summarize_manageability(mgmt: list[str]) -> list[str]:
    out: list[str] = []
    for line in mgmt:
        candidate = normalize_manageability_value(line)
        if candidate:
            out.append(candidate)
    return unique_preserve(out)


MATERIAL_ITEM_SPLIT_PATTERNS = [
    re.compile(r"\s+(?=(?:Up to\s+)?\d+% PCC recycled plastic\b)", re.I),
    re.compile(r"\s+(?=(?:Up to\s+)?\d+% post-consumer recycled plastic\b)", re.I),
    re.compile(r"\s+(?=(?:Up to\s+)?\d+% recycled plastic\b)", re.I),
    re.compile(r"\s+(?=100% plastic[- ]free\b)", re.I),
]


def split_environmental_line(line: str) -> list[str]:
    fragments = [line]
    for pattern in MATERIAL_ITEM_SPLIT_PATTERNS:
        next_fragments: list[str] = []
        for fragment in fragments:
            parts = [part.strip() for part in pattern.split(fragment) if part.strip()]
            next_fragments.extend(parts or [fragment])
        fragments = next_fragments
    return fragments


def summarize_environmental(env: list[str]) -> list[str]:
    lines = slice_after_exact_label(env, ["Material", "Material[1]"], ["CERTIFICATIONS", "Green Certifications"])
    out = []
    for line in lines:
        lowered = line.lower()
        if "pcc:" in lowered or "recycled materials from customers" in lowered:
            continue
        if "100% plastic free" in lowered and "adapter" in lowered:
            match = re.search(r"100% Plastic Free.*", line)
            if match:
                left = line[: match.start()].strip()
                right = line[match.start() :].strip()
                if left:
                    out.append(left)
                if right:
                    out.append(right)
                continue
            continue
        if any(token in lowered for token in ["recycled", "plastic free", "sustainable", "fsc", "packaging", "rare earth", "obp"]):
            out.extend(split_environmental_line(line))
    return unique_preserve(out)


def summarize_certifications(cert: list[str]) -> tuple[list[str], list[str], str]:
    green = slice_after_exact_label(cert, ["Green Certifications", "Green Certifications[1]", "Green Certifications[2]"], ["Other Certifications", "Mil-Spec Test"])
    other: list[str] = []
    in_other = False
    for line in cert:
        lowered = line.lower()
        normalized = normalize_label_token(line)
        if normalized == "other certifications":
            in_other = True
            continue
        if lowered.startswith("other certifications"):
            in_other = True
            tail = re.sub(r"^Other Certifications\s*", "", line, flags=re.I).strip()
            if tail:
                other.append(tail)
            continue
        if not in_other:
            continue
        if lowered.startswith("feature with ") or lowered.startswith("lenovo reserves the right"):
            break
        other.append(line)

    green_out: list[str] = []
    for line in green:
        lowered = line.lower()
        if is_noise_line(line):
            continue
        if any(token in lowered for token in ["please visit", "please see", "only available on the models", "the items listed under"]):
            continue
        cleaned = re.sub(r"^Green Certifications(?:\[\d+\])?\s*", "", line, flags=re.I).strip()
        if not cleaned:
            continue
        if "tco certified" in lowered and "rohs compliant" in lowered:
            tco_match = re.search(r"(TCO Certified.*?)(?:\s+RoHS compliant.*|$)", cleaned, re.I)
            if tco_match:
                green_out.append(tco_match.group(1).strip())
            green_out.append("RoHS compliant")
            continue
        if any(token in lowered for token in ["energy star", "epeat", "erp", "tco", "rohs"]):
            green_out.append(cleaned)

    other_out: list[str] = []
    for line in other:
        lowered = line.lower()
        if is_noise_line(line):
            continue
        cleaned = re.sub(r"^Other Certifications(?:\[\d+\])?\s*", "", line, flags=re.I).strip()
        if not cleaned:
            continue
        if "mil-std-810h" in lowered:
            continue
        if "mil-std-810g" in lowered:
            continue
        if any(token in lowered for token in ["eyesafe", "tüv", "tuv", "intel evo", "sgs", "dynamic privacy"]):
            other_out.append(cleaned.replace("(Optional) ", ""))

    milstd = ""
    all_text = " ".join(cert)
    if "MIL-STD-810H" in all_text:
        milstd = "MIL-STD-810H"
    elif "MIL-STD-810G" in all_text:
        milstd = "MIL-STD-810G"

    return unique_preserve(green_out), unique_preserve(other_out), milstd


def format_section_heading(name: str, heading_style: str) -> str:
    if heading_style == "legacy":
        return name.title().replace(" & ", " & ")
    return name


def format_field_label(name: str, heading_style: str) -> str:
    if heading_style == "legacy":
        return name.title().replace("Wxdxh", "WxDxH")
    return name


def append_field(lines: list[str], heading_style: str, label: str, values: list[str]) -> None:
    values = [value for value in values if value]
    if not values:
        return
    lines.append(format_field_label(label, heading_style))
    lines.extend(values)


def build_shortdesc(product_name: str, spec_text: str, output_mode: str, heading_style: str) -> str:
    lines = split_lines(spec_text)
    sections = split_sections(lines)
    resolved_output_mode = "psref_wrapped" if output_mode == "auto" else output_mode

    out: list[str] = []
    if resolved_output_mode == "psref_wrapped":
        out.extend(["PSREF", "Product Specifications", "Reference", ""])
    elif heading_style == "legacy":
        out.append(product_name.replace("_", " "))

    perf = sections.get("PERFORMANCE", [])
    design = sections.get("DESIGN", [])
    conn = sections.get("CONNECTIVITY", [])
    sec = sections.get("SECURITY & PRIVACY", [])
    mgmt = sections.get("MANAGEABILITY", [])
    env = sections.get("ENVIRONMENTAL", [])
    cert = sections.get("CERTIFICATIONS", [])

    body: list[str] = []

    performance_lines: list[str] = []
    append_field(performance_lines, heading_style, "Processor", extract_processor(perf))
    append_field(performance_lines, heading_style, "AI PC Category", extract_ai_category(perf))
    append_field(performance_lines, heading_style, "NPU", extract_npu(perf))
    append_field(performance_lines, heading_style, "Operating System", extract_operating_system(perf))
    append_field(performance_lines, heading_style, "Graphics", extract_graphics(perf))
    append_field(performance_lines, heading_style, "Memory", summarize_memory(perf))
    append_field(performance_lines, heading_style, "Storage", summarize_storage(perf))
    append_field(performance_lines, heading_style, "Audio", summarize_audio(perf))
    camera_label, camera_values = summarize_camera(perf)
    append_field(performance_lines, heading_style, camera_label, camera_values)
    append_field(performance_lines, heading_style, "Battery", summarize_battery(perf))
    adapter_label, adapter_values = summarize_power_adapter(perf)
    append_field(performance_lines, heading_style, adapter_label, adapter_values)
    if performance_lines:
        body.append(format_section_heading("PERFORMANCE", heading_style))
        body.extend(performance_lines)

    design_lines: list[str] = []
    append_field(design_lines, heading_style, "Display", render_display_offerings(design))
    append_field(design_lines, heading_style, "Screen-to-Body Ratio", summarize_screen_to_body(design))
    append_field(design_lines, heading_style, "Multi-mode", summarize_multimode(design))
    append_field(design_lines, heading_style, "Pen", summarize_pen(design))
    append_field(design_lines, heading_style, "Keyboard", summarize_keyboard(design))
    append_field(design_lines, heading_style, "Touchpad", summarize_touchpad(design))
    append_field(design_lines, heading_style, "Dimensions (WxDxH)", summarize_dimensions(design))
    append_field(design_lines, heading_style, "Weight", summarize_weight(design))
    append_field(design_lines, heading_style, "Color", summarize_color(design))
    append_field(design_lines, heading_style, "Case Material", summarize_case_material(design))
    if design_lines:
        body.append(format_section_heading("DESIGN", heading_style))
        body.extend(design_lines)

    connectivity_lines: list[str] = []
    append_field(connectivity_lines, heading_style, "Ethernet", summarize_ethernet(conn))
    append_field(connectivity_lines, heading_style, "WLAN + Bluetooth", summarize_wlan(conn))
    wwan_label, wwan_values = summarize_wwan(conn)
    append_field(connectivity_lines, heading_style, wwan_label, wwan_values)
    append_field(connectivity_lines, heading_style, "NFC", summarize_nfc(conn))
    append_field(connectivity_lines, heading_style, "Ports", summarize_ports(conn))
    append_field(connectivity_lines, heading_style, "Docking", summarize_docking(conn))
    if connectivity_lines:
        body.append(format_section_heading("CONNECTIVITY", heading_style))
        body.extend(connectivity_lines)

    security_lines: list[str] = []
    append_field(security_lines, heading_style, "Security", summarize_security(sec))
    if security_lines:
        body.append(format_section_heading("SECURITY & PRIVACY", heading_style))
        body.extend(security_lines)

    manageability_values = summarize_manageability(mgmt)
    if manageability_values:
        body.append(format_section_heading("MANAGEABILITY", heading_style))
        if heading_style == "legacy":
            body.extend(manageability_values)
        else:
            append_field(body, heading_style, "System Management", manageability_values)

    environmental_values = summarize_environmental(env)
    if environmental_values:
        body.append(format_section_heading("ENVIRONMENTAL", heading_style))
        append_field(body, heading_style, "Material", environmental_values)

    green_values, other_values, milstd = summarize_certifications(cert)
    if milstd:
        other_values = unique_preserve(other_values + [milstd])
    if green_values or other_values:
        body.append(format_section_heading("CERTIFICATIONS", heading_style))
        append_field(body, heading_style, "Green Certifications", green_values)
        append_field(body, heading_style, "Other Certifications", other_values)

    out.extend(body)

    if resolved_output_mode == "psref_wrapped":
        out.extend(
            [
                "",
                "Note:",
                "Feature with * is optional and only configured on selected models.",
                "The specifications on this page may not be available in all regions, and may be changed or updated without notice.",
            ]
        )

    return sanitize_generation_text("\n".join(out))


def write_manifest(
    results: list[GenerationResult],
    workbook_path: Path,
    output_mode: str,
    heading_style: str,
    workbook_layout: str,
) -> None:
    manifest_path = workbook_path.with_suffix(".json")
    payload = {
        "workbook": str(workbook_path),
        "generator": "rule_based",
        "output_mode": output_mode,
        "heading_style": heading_style,
        "workbook_layout": workbook_layout,
        "results": [
            {
                "product": result.product,
                "source_path": result.source_path,
                "mode": result.mode,
                "error": result.error,
            }
            for result in results
        ],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Lenovo short specs without an AI model and save them to one Excel workbook."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--spec-files",
        "--spec-pdfs",
        dest="spec_pdfs",
        nargs="+",
        help="One or more spec PDF/TXT files to process.",
    )
    source_group.add_argument("--spec-dir", help="Directory containing spec files.")
    parser.add_argument("--glob", default="*_Spec.PDF", help="Glob used with --spec-dir. Default: *_Spec.PDF")
    parser.add_argument("--output-xlsx", required=True, help="Path to the output Excel workbook.")
    parser.add_argument(
        "--workbook-layout",
        choices=["per_product", "single_sheet_summary"],
        default="per_product",
        help="Workbook layout. per_product=one worksheet per product; single_sheet_summary=all products in one worksheet.",
    )
    parser.add_argument(
        "--output-mode",
        choices=["auto", "psref_wrapped", "content_only"],
        default="auto",
        help="ShortDesc output wrapper mode.",
    )
    parser.add_argument(
        "--heading-style",
        choices=["modern", "legacy"],
        default="modern",
        help="Section heading style. modern=uppercase, legacy=title case with product name header.",
    )
    parser.add_argument(
        "--runtime-text-dir",
        default="analysis_output/runtime_spec_text_rule_based",
        help="Directory used to cache extracted spec text files.",
    )
    parser.add_argument(
        "--generated-text-dir",
        default="analysis_output/generated_shortspec_batch_rule_based",
        help="Directory used to save generated per-product text outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    runtime_text_dir = Path(args.runtime_text_dir).resolve()
    runtime_manifest = runtime_text_dir.parent / "runtime_spec_text_rule_based_manifest.json"
    generated_text_dir = Path(args.generated_text_dir).resolve()
    workbook_path = Path(args.output_xlsx).resolve()

    products = load_product_specs(spec_paths, runtime_text_dir, runtime_manifest)

    results: list[GenerationResult] = []
    sheets: list[tuple[str, str]] = []
    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.source_path}")
        try:
            shortdesc_text = build_shortdesc(
                product_name=product.product,
                spec_text=product.spec_text,
                output_mode=args.output_mode,
                heading_style=args.heading_style,
            )
            result = GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="rule_based",
                shortdesc_text=shortdesc_text,
                usage=None,
                response_id=None,
            )
        except Exception as exc:
            result = GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="error",
                shortdesc_text=f"ERROR\nProduct\n{product.product}\nDetails\n{exc}",
                usage=None,
                response_id=None,
                error=str(exc),
            )

        results.append(result)
        sheets.append((product.display_name, result.shortdesc_text))

    save_generation_texts(results, generated_text_dir)
    write_xlsx(workbook_path, sheets, workbook_layout=args.workbook_layout)
    write_manifest(results, workbook_path, args.output_mode, args.heading_style, args.workbook_layout)

    failures = [result for result in results if result.error]
    print(f"WORKBOOK\t{workbook_path}")
    print(f"SHEETS\t{1 if args.workbook_layout == 'single_sheet_summary' else len(sheets)}")
    print(f"FAILURES\t{len(failures)}")
    if failures:
        for failure in failures:
            print(f"FAILED\t{failure.product}\t{failure.error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
