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
    derive_display_name,
    derive_product_name,
    extract_pdf_texts,
    normalize_text,
    sanitize_sheet_name,
    write_xlsx,
)


TOP_LEVEL_SECTIONS = [
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "SECURITY & PRIVACY",
    "MANAGEABILITY",
    "SERVICE",
    "ENVIRONMENTAL",
    "CERTIFICATIONS",
]

DT_L2_LABELS = {
    "Processor",
    "AI PC Category",
    "NPU",
    "Operating System",
    "Graphics",
    "Chipset",
    "Memory",
    "Storage",
    "Optical",
    "Audio",
    "Camera",
    "Power Supply",
    "Display",
    "Form Factor",
    "Dimensions (WxDxH)",
    "Weight",
    "Color",
    "Chassis",
    "Bays",
    "Expansion Slots",
    "Cooling System (Fan & Cooler)",
    "Stand",
    "Mounting",
    "Other Design",
    "Ethernet",
    "WLAN + Bluetooth",
    "Front Ports",
    "Rear Ports",
    "Top Ports",
    "Left Ports",
    "Right Ports",
    "Optional Ports",
    "Security",
    "System Management",
    "Base Warranty",
    "Material",
    "Green Certifications",
    "Other Certifications",
}

SECTION_HEADINGS = {
    "OVERVIEW",
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "SECURITY & PRIVACY",
    "SECURITY AND PRIVACY",
    "MANAGEABILITY",
    "SERVICE",
    "ENVIRONMENTAL",
    "CERTIFICATIONS",
    "ACCESSORIES",
    "OPERATING REQUIREMENTS",
}

FIELD_LABELS = {
    "Processor",
    "Processor Family",
    "Processor**",
    "AI PC Category",
    "NPU",
    "AI (Artificial Intelligence)",
    "Operating System",
    "Operating System**",
    "Graphics",
    "Graphics**",
    "Monitor Support",
    "Chipset",
    "Max Memory",
    "Memory Slots",
    "Memory Type",
    "Memory Protection",
    "Storage",
    "Max Storage Support",
    "Storage Support",
    "Storage Type",
    "Storage Type**",
    "Storage Type***",
    "RAID",
    "Removable Storage",
    "Optical",
    "Optical**",
    "Card Reader",
    "Multi-Media",
    "Audio Chip",
    "Speakers",
    "Microphone",
    "Camera",
    "Camera**",
    "Power Supply",
    "Power Supply**",
    "Display",
    "Display**",
    "Touchscreen",
    "Input Device",
    "Keyboard",
    "Keyboard**",
    "Mouse",
    "Mouse**",
    "Mechanical",
    "Form Factor",
    "Dimensions (WxDxH)",
    "Packaging Dimensions (WxDxH)",
    "Weight",
    "Packaging Weight",
    "Case Color",
    "Chassis",
    "Chassis**",
    "Bays",
    "Expansion Slots",
    "Cooling System (Fan & Cooler)",
    "Cooling System (Fan & Cooler)***",
    "System Lighting",
    "EOU",
    "Stand",
    "IO Box",
    "IO BOX",
    "Mounting",
    "Others",
    "Network",
    "WLAN + Bluetooth",
    "WLAN + Bluetooth**",
    "Onboard Ethernet",
    "Optional Ethernet",
    "Ports",
    "Front Ports",
    "Optional Front Ports",
    "Rear Ports",
    "Rear Ports**",
    "Optional Rear Ports",
    "Optional Rear Ports**",
    "Top Ports",
    "Left Ports",
    "Optional Left Ports",
    "Right Ports",
    "Optional Right Ports",
    "Security",
    "Security Chip",
    "Physical Locks",
    "Chassis Intrusion Switch",
    "Fingerprint Reader",
    "BIOS Security",
    "System Management",
    "Warranty",
    "Base Warranty",
    "Base Warranty**",
    "Sustainability",
    "Material",
    "Green Certifications",
    "Other Certifications",
    "Mil-Spec Test",
}

@dataclass(frozen=True)
class ProductSpec:
    product: str
    display_name: str
    source_path: Path
    spec_text: str
    profile: str


def clean_line(line: str) -> str:
    line = normalize_text(line)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = line.replace("\u00a0", " ")
    for old, new in {
        "®": "",
        "™": "",
        "©": "",
        "USB-C®": "USB-C",
        "Wi-Fi®": "Wi-Fi",
        "Bluetooth®": "Bluetooth",
        "DisplayPort™": "DisplayPort",
        "AMD Ryzen™": "AMD Ryzen",
        "AMD Radeon™": "AMD Radeon",
        "Intel®": "Intel",
        "Core™": "Core",
        "NVIDIA®": "NVIDIA",
        "GeForce RTX™": "GeForce RTX",
        "HDMI®": "HDMI",
        "Lenovo®": "Lenovo",
    }.items():
        line = line.replace(old, new)
    line = line.replace("−", "-").replace("–", "-").replace("—", "-")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def split_lines(text: str) -> list[str]:
    return [clean_line(line) for line in normalize_text(text).splitlines() if clean_line(line)]


def strip_stars_and_notes(label: str) -> str:
    label = re.sub(r"\[[0-9,\s]+\]", "", label)
    return re.sub(r"\*+$", "", label).strip()


FIELD_LABEL_KEYS = {strip_stars_and_notes(label).lower() for label in FIELD_LABELS}

WORD_NUMBERS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
}


def label_key(line: str) -> str:
    return strip_stars_and_notes(line).lower()


def is_section_heading(line: str) -> bool:
    return line.upper() in SECTION_HEADINGS


def is_probable_page_noise(line: str) -> bool:
    if not line:
        return True
    if line in {"PSREF", "Product Specifications", "Reference", "/"}:
        return True
    if re.search(r"\b\d+ of \d+\b", line):
        return True
    if re.search(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\s+\d{4}\b",
        line,
    ):
        return True
    lowered = line.lower()
    if lowered.startswith("notes:") or lowered == "notes":
        return True
    if lowered.startswith("feature with "):
        return True
    if lowered.startswith("items with *"):
        return True
    if lowered.startswith("the specifications on this page"):
        return True
    if lowered.startswith("lenovo reserves the right"):
        return True
    if lowered.startswith("please refer"):
        return True
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return True
    if re.match(r"^(?:IdeaCentre|ThinkCentre|Legion)\s+.+$", line):
        return True
    return False


def is_stop_line(line: str, stop_labels: set[str]) -> bool:
    if is_section_heading(line):
        return True
    key = label_key(line)
    return key in stop_labels


def find_label_index(lines: list[str], labels: Iterable[str], start: int = 0) -> int | None:
    normalized = {label.lower() for label in labels}
    for index in range(start, len(lines)):
        if label_key(lines[index]) in normalized:
            return index
    return None


def slice_after_label(lines: list[str], labels: Iterable[str], stop_labels: Iterable[str]) -> list[str]:
    start = find_label_index(lines, labels)
    if start is None:
        return []
    stops = {label.lower() for label in stop_labels}
    captured: list[str] = []
    for line in lines[start + 1 :]:
        if line.lower().startswith("notes"):
            break
        if is_stop_line(line, stops):
            break
        if is_probable_page_noise(line):
            continue
        if label_key(line) in FIELD_LABEL_KEYS:
            continue
        captured.append(line)
    return captured


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


def normalize_value(value: str) -> str:
    value = clean_line(value)
    value = value.strip(" •")
    value = value.replace("TMDS", "TMDS")
    value = value.replace("Wifi", "Wi-Fi")
    value = value.replace("wifi", "Wi-Fi")
    value = re.sub(r"\bNo support\b", "", value, flags=re.I).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def filter_values(values: Iterable[str], *, keep_optional_star: bool = False) -> list[str]:
    result = []
    for value in values:
        raw = clean_line(value)
        optional = raw.endswith("•") or raw.endswith("*")
        value = normalize_value(raw)
        lowered = value.lower()
        if not value:
            continue
        if lowered.startswith("no ") or lowered in {"none", "-", "n/a"}:
            continue
        if lowered in {"models dimensions", "models weight", "power type efficiency key features"}:
            continue
        if keep_optional_star and optional and not value.endswith("*"):
            value += "*"
        result.append(value)
    return unique_preserve(result)


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pypdf is not installed and no cached text was available. "
            "Use a runtime text cache or run on a machine with Microsoft Word for PDF extraction."
        ) from exc

    reader = PdfReader(str(path))
    return normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))


def infer_profile(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.stem.lower()
    if "legion" in parts or name.startswith("legion"):
        return "Legion"
    if "thinkcentre" in parts or name.startswith("thinkcentre"):
        return "ThinkCentre"
    if "ideacentre" in parts or name.startswith("ideacentre"):
        return "IdeaCentre"
    return "DT"


def load_product_specs(paths: list[Path], runtime_text_dir: Path | None) -> list[ProductSpec]:
    pdf_paths = [path for path in paths if path.suffix.lower() == ".pdf"]
    cached_texts: dict[Path, str] = {}
    missing_pdf_paths: list[Path] = []

    if runtime_text_dir:
        for path in pdf_paths:
            cache_path = runtime_text_dir / f"{path.name}.txt"
            if cache_path.exists():
                cached_texts[path] = normalize_text(cache_path.read_text(encoding="utf-8"))
            else:
                missing_pdf_paths.append(path)
    else:
        missing_pdf_paths = pdf_paths

    extracted_texts: dict[Path, str] = {}
    if missing_pdf_paths:
        try:
            for path in missing_pdf_paths:
                extracted_texts[path] = read_pdf_text(path)
                if runtime_text_dir:
                    runtime_text_dir.mkdir(parents=True, exist_ok=True)
                    (runtime_text_dir / f"{path.name}.txt").write_text(extracted_texts[path], encoding="utf-8")
        except RuntimeError:
            if not runtime_text_dir:
                raise
            manifest_path = runtime_text_dir.parent / "runtime_spec_text_rule_based_dt_manifest.json"
            extracted_texts = extract_pdf_texts(missing_pdf_paths, runtime_text_dir, manifest_path)

    products: list[ProductSpec] = []
    for path in paths:
        if path.suffix.lower() == ".pdf":
            text = cached_texts.get(path) or extracted_texts[path]
        else:
            text = normalize_text(path.read_text(encoding="utf-8"))
        products.append(
            ProductSpec(
                product=derive_product_name(path),
                display_name=derive_display_name(path),
                source_path=path,
                spec_text=text,
                profile=infer_profile(path),
            )
        )
    return products


def format_or_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} or {items[1]}"
    return f"{', '.join(items[:-1])}, or {items[-1]}"


def normalize_generation_phrase(value: str) -> str:
    return value


def summarize_processor(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Processor Family"], ["Processor**", "Processor", "AI PC Category", "Operating System"])
    values = filter_values(values)
    cleaned = []
    for value in values:
        value = re.sub(r"\s+Processor$", "", value)
        value = value.replace("Intel Celeron, Intel Pentium, or", "Intel Celeron, Pentium, or")
        value = normalize_generation_phrase(value)
        value = re.sub(r"\bIntel Core Ultra\b", "Intel Core Ultra", value, flags=re.I)
        value = re.sub(r"\bIntel Core\b", "Intel Core", value, flags=re.I)
        cleaned.append(value)
    return unique_preserve(cleaned[:3])


def summarize_ai_category(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["AI PC Category"], ["NPU", "Operating System"])
    result = []
    for value in filter_values(values):
        if value.lower() == "non-ai pc":
            continue
        result.append(value)
    return unique_preserve(result[:3])


def summarize_npu(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["NPU"], ["Notes", "Operating System"])
    result = []
    for value in filter_values(values):
        value = re.sub(r"\s*\([^)]*\)", "", value)
        result.append(value)
    return unique_preserve(result[:2])


def summarize_operating_system(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Operating System**", "Operating System"], ["Graphics", "Monitor Support"])
    result = []
    for value in filter_values(values):
        if value.lower().startswith("no preload"):
            continue
        value = value.replace("Windows 10 Home 64 Single Language", "Windows 10 Home 64")
        result.append(value)
    result = unique_preserve(result)
    lowered = {value.lower() for value in result}
    if "windows 11 pro" in lowered and "windows 11 home" in lowered:
        merged = ["Windows 11 Pro or Home"]
        for value in result:
            if value.lower() in {"windows 11 pro", "windows 11 home", "windows 11 home single language"}:
                continue
            merged.append(value)
        result = unique_preserve(merged)
    return result


def summarize_graphics(lines: list[str], profile: str) -> list[str]:
    graphics = slice_after_label(lines, ["Graphics**", "Graphics"], ["Monitor Support", "Chipset"])
    blob = " ".join(graphics)
    found: list[str] = []
    patterns = [
        r"Intel UHD Graphics(?: \d+)?",
        r"Intel Iris Xe Graphics",
        r"Intel Graphics",
        r"AMD Radeon Graphics",
        r"AMD Radeon RX \d+[A-Z0-9 ]*",
        r"NVIDIA GeForce RTX \d+(?: Ti)?(?: SUPER)?(?: \d+GB)?",
        r"NVIDIA T\d+",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, blob, flags=re.I):
            value = clean_line(match)
            value = re.sub(r"\bgraphics\s+\d{3,4}\b", "Graphics", value, flags=re.I)
            value = re.sub(r"\s+Discrete\s+\d+GB.*$", "", value, flags=re.I)
            if re.match(r"Intel|AMD", value, flags=re.I):
                if "(integrated)" not in value.lower() and not value.lower().startswith("amd radeon rx"):
                    value = f"{value} (integrated)"
            found.append(value)
    if profile == "Legion":
        found = [value for value in found if "Integrated" not in value and "(integrated)" not in value] or found
    return unique_preserve(found[:10])


def summarize_chipset(lines: list[str]) -> list[str]:
    result = []
    for value in filter_values(slice_after_label(lines, ["Chipset"], ["Memory", "Max Memory"])):
        result.append(value)
    return result[:2]


def summarize_memory(lines: list[str]) -> list[str]:
    max_memory = filter_values(slice_after_label(lines, ["Max Memory"], ["Memory Slots", "Memory Type"]))
    slots = filter_values(slice_after_label(lines, ["Memory Slots"], ["Memory Type", "Memory Protection", "Storage"]))
    memory_type = filter_values(slice_after_label(lines, ["Memory Type", "Memory Type**"], ["Memory Protection", "Storage"]))

    if not max_memory and not slots:
        return []

    max_value = max_memory[0] if max_memory else ""
    slot_value = slots[0] if slots else ""
    type_value = memory_type[-1] if memory_type else ""

    max_value = re.sub(r"\s*\([^)]*(?:DDR|LPDDR|SODIMM|SO-DIMM|UDIMM|DIMM)[^)]*\)", "", max_value, flags=re.I)
    if "lpddr" in max_value.lower() and "soldered" in max_value.lower():
        capacity_match = re.search(r"\b\d+GB\b", max_value, flags=re.I)
        type_match = re.search(r"LPDDR\dX?-\d+(?:\s+MoP)?", max_value, flags=re.I)
        if capacity_match and type_match:
            return [f"{capacity_match.group(0)} {type_match.group(0)}, soldered"]
    max_value = re.sub(r"\s+", " ", max_value).strip(" ,")
    if type_value and not re.search(r"(?:DDR|LPDDR)\d[^\s,]*-\d+", max_value, flags=re.I):
        type_match = re.search(r"(?:DDR|LPDDR)\d[^\s,]*-\d+", type_value, flags=re.I)
        if type_match:
            max_value = f"{max_value} {type_match.group(0)}"

    slot_raw = slot_value
    slot_value = re.sub(r",?\s*dual-channel capable", "", slot_value, flags=re.I)
    slot_value = re.sub(r"\bSO-DIMM\b", "SODIMM", slot_value, flags=re.I)
    slot_value = re.sub(r"\b([A-Za-z]+)\s+(?:DDR|LPDDR)\d[^\s,]*\s+(SODIMM|UDIMM|DIMM)\s+slots\b", r"\1 \2 slots", slot_value, flags=re.I)
    slot_value = re.sub(
        r"^(One|Two|Three|Four|Five|Six)\b",
        lambda match: match.group(1).lower(),
        slot_value,
        flags=re.I,
    )
    slot_value = re.sub(r"\s+", " ", slot_value).strip(" ,")

    if max_value and slot_value:
        ddr4_sodimm = re.search(r"\b(Two|2)\s+DDR4\s+SO-?DIMM\s+slots\b", slot_raw, flags=re.I)
        if ddr4_sodimm:
            return [f"{max_value} with two DDR4 SO-DIMM slots"]
        return [f"{max_value}, {slot_value}"]
    return [max_value or slot_value]


def summarize_storage(lines: list[str]) -> list[str]:
    values = slice_after_label(
        lines,
        ["Max Storage Support", "Storage Support"],
        ["Storage Type", "Storage Type**", "Storage Type***", "RAID", "Removable Storage"],
    )
    return filter_values(values)[:6]


def summarize_optical(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["Optical**", "Optical"], ["Card Reader", "Multi-Media"]))
    blob = " ".join(values).lower()
    has_rom = "dvd-rom" in blob
    has_rw = "dvd" in blob and ("±rw" in blob or "+/-rw" in blob or "burner" in blob)
    if has_rom and has_rw:
        return ["DVD-ROM or DVD±RW*"]
    if has_rw:
        return ["DVD+/-RW*"]
    if has_rom:
        return ["DVD-ROM*"]
    return []


def summarize_audio(lines: list[str]) -> list[str]:
    values = []
    values.extend(slice_after_label(lines, ["Audio Chip"], ["Speakers", "Microphone", "Camera", "Power Supply"]))
    values.extend(slice_after_label(lines, ["Speakers"], ["Microphone", "Camera", "Power Supply"]))
    values.extend(slice_after_label(lines, ["Microphone"], ["Camera", "Power Supply"]))
    result = []
    for value in filter_values(values):
        lowered = value.lower()
        if value.lower().startswith("24-bit"):
            continue
        if not any(
            token in lowered
            for token in (
                "high definition",
                "speaker",
                "microphone",
                "audio by",
                "harman",
                "dolby",
                "array",
            )
        ):
            continue
        value = re.sub(r",?\s*Realtek.*", "", value).strip()
        result.append(value)
    return unique_preserve(result[:6])


def summarize_camera(lines: list[str]) -> list[str]:
    result = []
    for value in filter_values(slice_after_label(lines, ["Camera**", "Camera"], ["Power Supply", "DESIGN"])):
        value = re.sub(r",?\s*fixed focus", "", value, flags=re.I)
        value = re.sub(r"^5\.0-megapixel IR camera,\s*with AI chip$", "IR & 5.0-megapixel with AI chip", value, flags=re.I)
        value = re.sub(r"^5\.0-megapixel IR camera$", "IR & 5.0-megapixel", value, flags=re.I)
        value = re.sub(r"^5\.0-megapixel IR camera\*$", "5.0-megapixel IR camera*", value, flags=re.I)
        result.append(value)
    return unique_preserve(result[:5])


def summarize_power_supply(lines: list[str], profile: str) -> list[str]:
    values = slice_after_label(lines, ["Power Supply**", "Power Supply"], ["DESIGN", "Input Device"])
    result = []
    for value in values:
        optional = value.endswith("*")
        value = normalize_value(value)
        if not value or value.lower().startswith("power type") or value.lower().startswith("no "):
            continue
        match = re.match(r"(?P<w>\d+W)\s+(?P<type>Adapter|Fixed)\s+(?P<eff>\d+%)", value, flags=re.I)
        if match:
            power_type = match.group("type").lower()
            suffix = "*" if optional else ""
            if power_type == "adapter":
                result.append(f"{match.group('w')} {match.group('eff')} adapter{suffix}")
            elif profile == "Legion":
                result.append(f"{match.group('w')} {match.group('eff')} Fixed")
            else:
                result.append(f"{match.group('w')} {match.group('eff')} PSU")
            continue
        value = re.sub(r"^(?P<w>\d+W)\s+Adapter\s+-\s+-$", r"\g<w> adapter", value, flags=re.I)
        result.append(value)
    return unique_preserve(result[:8])


def summarize_display(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Display**", "Display"], ["Touchscreen", "Input Device", "Keyboard"])
    blob = " ".join(values)
    rows: list[str] = []
    for match in re.finditer(
        r'(?P<size>\d{2}(?:\.\d+)?"\s+(?:FHD|QHD|UHD|WQHD)?\s*\([^)]*\)).{0,120}?(?P<type>IPS|VA|TN|OLED)?',
        blob,
        flags=re.I,
    ):
        text = clean_line(match.group(0))
        text = re.sub(r"\s+", " ", text)
        if "nits" in text.lower() or "IPS" in text or "FHD" in text or "QHD" in text:
            rows.append(text)
    return unique_preserve(rows[:6])


def summarize_simple_field(lines: list[str], labels: list[str], stops: list[str], limit: int = 6) -> list[str]:
    return filter_values(slice_after_label(lines, labels, stops), keep_optional_star=True)[:limit]


def summarize_dimensions(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Dimensions (WxDxH)"], ["Packaging Dimensions (WxDxH)", "Weight"])
    result = []
    for value in values:
        value = normalize_value(value)
        if not value or value.lower() == "models dimensions":
            continue
        value = re.sub(r",?\s*with rubber feet\b", "", value, flags=re.I)
        value = re.sub(r",?\s*no stand\b", "", value, flags=re.I)
        value = re.sub(r",?\s*with ODD\b", "", value, flags=re.I)
        value = re.sub(r",?\s*with camera\b", "", value, flags=re.I)
        value = re.sub(r"\s+", " ", value).strip(" ,")
        if re.search(r"\d+\s*x\s*\d+", value, flags=re.I):
            result.append(value)
    return unique_preserve(result[:6])


def summarize_weight(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Weight"], ["Packaging Weight", "Case Color", "Chassis", "Bays"])
    result = []
    for value in values:
        value = normalize_value(value)
        if not value or value.lower() == "models weight":
            continue
        value = re.sub(r"^Models with stand\s+", "", value, flags=re.I)
        if "kg" in value.lower() or "lbs" in value.lower():
            value = re.sub(r"^(Non-touch|Touch models|Touch|Tiny only|With VESA[^:]*?)\s+", r"\1: ", value, flags=re.I)
            if not value.lower().startswith(("around", "all models", "fhd", "qhd", "tiny", "with", "non-touch", "touch")):
                value = f"Around {value}"
            result.append(value)
    return unique_preserve(result[:6])


def summarize_color(lines: list[str], profile: str) -> list[str]:
    values = slice_after_label(lines, ["Case Color"], ["Chassis", "Bays", "Expansion Slots", "EOU"])
    candidates = filter_values(values)
    if profile == "IdeaCentre" and not any(value.lower() == "luna grey" for value in candidates):
        return []
    result = []
    for value in candidates:
        if value.lower() in {"models", "color"}:
            continue
        if profile == "IdeaCentre" and value.lower() in {"mineral grey"}:
            continue
        if profile == "ThinkCentre" and value.lower() == "raven black":
            value = "Black"
        result.append(value.capitalize() if value.islower() else value)
    return unique_preserve(result[:4])


def normalize_optional_tail(value: str) -> str:
    optional = value.endswith("*") or "(optional" in value.lower()
    value = re.sub(r"\s*\([^)]*optional[^)]*\)", "", value, flags=re.I)
    value = re.sub(r"\s*\((?:length|height)[^)]*\)", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" ,")
    if re.match(r"One PCIe", value, flags=re.I):
        optional = False
        value = value.rstrip("*")
        value = re.sub(r",\s*(?:low-profile|full height)$", "", value, flags=re.I)
    if optional and not value.endswith("*"):
        value += "*"
    return value


def summarize_bays(lines: list[str]) -> list[str]:
    result = []
    for value in summarize_simple_field(lines, ["Bays"], ["Expansion Slots"], 8):
        result.append(normalize_optional_tail(value))
    return unique_preserve(result[:6])


def summarize_expansion_slots(lines: list[str]) -> list[str]:
    result = []
    for value in summarize_simple_field(
        lines,
        ["Expansion Slots"],
        ["Cooling System (Fan & Cooler)", "EOU", "Stand", "Mounting", "Others", "CONNECTIVITY"],
        12,
    ):
        result.append(normalize_optional_tail(value))
    return unique_preserve(result[:10])


def summarize_ethernet(lines: list[str], profile: str) -> list[str]:
    values = slice_after_label(lines, ["Onboard Ethernet"], ["Optional Ethernet", "WLAN + Bluetooth", "Ports", "Front Ports"])
    result = []
    for value in filter_values(values):
        if "2.5" in value or "2.5g" in value.lower():
            result.append("2.5GbE Gaming Onboard Ethernet" if profile == "Legion" else "2.5 Gigabit onboard Ethernet")
        elif "gigabit" in value.lower():
            result.append("Gigabit onboard Ethernet")
        else:
            result.append(value)
    return unique_preserve(result[:3])


def normalize_wlan_value(value: str) -> str:
    value = normalize_value(value)
    value = re.sub(r"\bDual Band\s+", "", value, flags=re.I)
    value = re.sub(r",?\s*Intel vPro technology support", "", value, flags=re.I)
    value = re.sub(r"\bM\.2 Card\b", "M.2 card", value, flags=re.I)
    if (
        re.search(r"\b802\.11ac\b", value, flags=re.I)
        and not re.search(r"\b802\.11ax\b|\b802\.11be\b", value, flags=re.I)
    ):
        bt = bluetooth_version(value)
        if bt:
            return f"802.11ac, Bluetooth {bt}"
    if re.search(r"\b802\.11ac\b", value, flags=re.I) and not re.search(r"\bWi-Fi\s*5\b", value, flags=re.I):
        value = f"Wi-Fi 5, {value}"
    if re.search(r"\b802\.11ax\b", value, flags=re.I) and not re.search(r"\bWi-Fi\s*(6|6E)\b", value, flags=re.I):
        value = f"Wi-Fi 6, {value}"
    if re.search(r"\b802\.11be\b", value, flags=re.I) and not re.search(r"\bWi-Fi\s*7\b", value, flags=re.I):
        value = f"Wi-Fi 7, {value}"
    value = re.sub(r"\s+", " ", value).strip(" ,")
    return value


def wifi_mark(value: str) -> str:
    lowered = value.lower()
    if "802.11be" in lowered or "wi-fi 7" in lowered:
        return "802.11be (Wi-Fi 7)"
    if "wi-fi 6e" in lowered:
        return "802.11ax (Wi-Fi 6E)"
    if "wi-fi 6" in lowered or "802.11ax" in lowered:
        return "802.11ax (Wi-Fi 6)"
    if "802.11ac" in lowered or "wi-fi 5" in lowered:
        return "802.11ac"
    return ""


def bluetooth_version(value: str) -> str:
    match = re.search(r"Bluetooth\s+(\d+(?:\.\d+)?)", value, flags=re.I)
    return match.group(1) if match else ""


def summarize_wlan(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["WLAN + Bluetooth**", "WLAN + Bluetooth"], ["Onboard Ethernet", "Optional Ethernet", "Ports"])
    result = []
    for value in filter_values(values):
        normalized = normalize_wlan_value(value)
        if normalized:
            result.append(normalized)
    return unique_preserve(result[:8])


def summarize_ports(lines: list[str], label: str, optional: bool = False) -> list[str]:
    stop_by_label = {
        "Front Ports": ["Optional Front Ports", "Rear Ports", "Optional Rear Ports", "Top Ports", "Left Ports", "Right Ports", "SECURITY & PRIVACY"],
        "Optional Front Ports": ["Rear Ports", "Optional Rear Ports", "Top Ports", "Left Ports", "Right Ports", "SECURITY & PRIVACY"],
        "Rear Ports": ["Optional Rear Ports", "Top Ports", "Left Ports", "Right Ports", "SECURITY & PRIVACY"],
        "Optional Rear Ports": ["Top Ports", "Left Ports", "Right Ports", "SECURITY & PRIVACY"],
        "Top Ports": ["Left Ports", "Right Ports", "SECURITY & PRIVACY"],
        "Left Ports": ["Right Ports", "SECURITY & PRIVACY"],
        "Right Ports": ["SECURITY & PRIVACY"],
    }
    values = slice_after_label(lines, [label, f"{label}**"], stop_by_label.get(label, ["SECURITY & PRIVACY"]))
    result = []
    for value in filter_values(values, keep_optional_star=optional):
        value = re.sub(r"\s*\(support data transfer and 5V@3A charging\)", " (5V/3A charging)", value, flags=re.I)
        value = re.sub(r"\s*\(one supports Always On and fast charge\)", "", value, flags=re.I)
        value = re.sub(r"\s*\(Always On and fast charge\)", "", value, flags=re.I)
        if optional:
            match = re.match(r"Optional port\s+(\d+)\s+\((?:one of\s+)?(.+?)\)\*?$", value, flags=re.I)
            if match:
                option = match.group(2).split("/")[0].strip()
                value = f"1x {option} (port {match.group(1)})*"
        result.append(value)
    return unique_preserve(result[:20])


def summarize_security(lines: list[str], profile: str) -> list[str]:
    values = []
    values.extend(slice_after_label(lines, ["Security Chip"], ["Physical Locks", "Chassis Intrusion Switch", "Fingerprint Reader", "BIOS Security"]))
    values.extend(slice_after_label(lines, ["Physical Locks"], ["Chassis Intrusion Switch", "Fingerprint Reader", "BIOS Security"]))
    values.extend(slice_after_label(lines, ["Chassis Intrusion Switch"], ["Fingerprint Reader", "BIOS Security", "MANAGEABILITY", "SERVICE"]))
    values.extend(slice_after_label(lines, ["Fingerprint Reader"], ["BIOS Security", "MANAGEABILITY", "SERVICE"]))
    result = []
    for value in filter_values(values, keep_optional_star=True):
        value = value.replace("Kensington Security Slot, 3 x 7 mm", "Kensington Security Slot")
        value = value.replace("Kensington Security Slot, 3 x 7 mm", "Kensington Security Slot")
        if "firmware tpm" in value.lower():
            if "soc" in value.lower():
                value = "Firmware TPM 2.0 integrated in SoC"
            else:
                value = "Firmware TPM 2.0 integrated in chipset"
        if "discrete tpm" in value.lower():
            value = "Discrete TPM 2.0"
        result.append(value)
    return unique_preserve(result[:8])


def summarize_manageability(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["System Management"], ["SERVICE", "CERTIFICATIONS"])
    result = []
    for value in filter_values(values, keep_optional_star=True):
        lowered = value.lower()
        if lowered.startswith("non-") or lowered == "system management":
            continue
        if "vpro" in lowered or "dash" in lowered or "manageability" in lowered:
            result.append(value)
    return unique_preserve(result[:5])


def summarize_base_warranty(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Base Warranty**", "Base Warranty"], ["Notes", "ACCESSORIES", "OPERATING REQUIREMENTS", "CERTIFICATIONS"])
    candidates: list[tuple[int, int, str]] = []
    for value in filter_values(values):
        lowered = value.lower()
        if "service" not in lowered and "warranty" not in lowered:
            continue
        year_match = re.search(r"(\d+)-year", value, flags=re.I)
        years = int(year_match.group(1)) if year_match else 0
        if "onsite" in lowered:
            normalized = f"Up to {years}-year limited onsite service"
            priority = 3
        elif any(token in lowered for token in ("courier", "carry-in", "depot", "mail-in")):
            normalized = f"Up to {years}-year depot service"
            priority = 2
        else:
            normalized = re.sub(r"^(\d+)-year", r"Up to \1-year", value)
            priority = 1
        candidates.append((years, priority, normalized))
    if not candidates:
        return []
    best_year = max(year for year, _, _ in candidates)
    best = sorted((item for item in candidates if item[0] == best_year), key=lambda item: item[1], reverse=True)[0]
    return [best[2]]


def normalize_certification_value(value: str) -> list[str]:
    optional = value.lower().startswith("(optional)") or value.endswith("*")
    value = re.sub(r"^\(Optional\)\s*", "", value, flags=re.I)
    value = normalize_value(value)
    pieces = []
    known_patterns = [
        r"ENERGY STAR\s*\d+(?:\.\d+)?",
        r"EPEAT (?:Gold|Silver) Registered",
        r"ErP Lot \d+(?:/\d+)?",
        r"RoHS compliant",
        r"TCO Certified(?:, generation \d+|\s*\d+(?:\.\d+)?)?",
    ]
    for pattern in known_patterns:
        for match in re.findall(pattern, value, flags=re.I):
            item = clean_line(match)
            if optional and not item.endswith("*"):
                item += "*"
            pieces.append(item)
    if pieces:
        return unique_preserve(pieces)
    if optional and value and not value.endswith("*"):
        value += "*"
    return [value] if value else []


def summarize_material(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Material"], ["CERTIFICATIONS", "Green Certifications"])
    return filter_values(values)[:10]


def summarize_green_certifications(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Green Certifications"], ["Other Certifications", "Notes"])
    result = []
    for value in filter_values(values):
        result.extend(normalize_certification_value(value))
    return unique_preserve(result[:12])


def summarize_other_certifications(lines: list[str]) -> list[str]:
    values = slice_after_label(lines, ["Other Certifications"], ["Notes"])
    result = []
    for value in filter_values(values):
        lowered = value.lower()
        if any(token in lowered for token in ("tüv", "tuv", "eyesafe", "mil-std", "ul ", "low noise", "energy")):
            mil = re.search(r"MIL-STD-\d+[A-Z]?", value, flags=re.I)
            if mil:
                result.append(mil.group(0).upper())
                continue
            value = re.sub(r"^\(Optional\)\s*", "", value, flags=re.I)
            if lowered.startswith("(optional)") and not value.endswith("*"):
                value += "*"
            result.append(value)
    for line in lines:
        if "MIL-STD" in line and not is_probable_page_noise(line):
            match = re.search(r"MIL-STD-\d+[A-Z]?", line)
            result.append(match.group(0).upper() if match else normalize_value(line))
    return unique_preserve(result[:12])


def append_field(rows: list[list[str]], l1: str, l2: str, values: list[str]) -> None:
    for value in values:
        if value:
            rows.append([l1, l2, value])


def rows_to_text(rows: list[list[str]]) -> str:
    out: list[str] = []
    current_l1 = ""
    current_l2 = ""
    for l1, l2, value in rows:
        if l1 != current_l1:
            out.append(l1)
            current_l1 = l1
            current_l2 = ""
        if l2 != current_l2:
            out.append(l2)
            current_l2 = l2
        out.append(value)
    return "\n".join(out)


def build_dt_rows(product_name: str, spec_text: str, profile: str) -> list[list[str]]:
    lines = split_lines(spec_text)
    rows: list[list[str]] = []

    append_field(rows, "PERFORMANCE", "Processor", summarize_processor(lines))
    append_field(rows, "PERFORMANCE", "AI PC Category", summarize_ai_category(lines))
    append_field(rows, "PERFORMANCE", "NPU", summarize_npu(lines))
    append_field(rows, "PERFORMANCE", "Operating System", summarize_operating_system(lines))
    append_field(rows, "PERFORMANCE", "Graphics", summarize_graphics(lines, profile))
    append_field(rows, "PERFORMANCE", "Chipset", summarize_chipset(lines))
    append_field(rows, "PERFORMANCE", "Memory", summarize_memory(lines))
    append_field(rows, "PERFORMANCE", "Storage", summarize_storage(lines))
    append_field(rows, "PERFORMANCE", "Optical", summarize_optical(lines))
    append_field(rows, "PERFORMANCE", "Audio", summarize_audio(lines))
    append_field(rows, "PERFORMANCE", "Camera", summarize_camera(lines))
    append_field(rows, "PERFORMANCE", "Power Supply", summarize_power_supply(lines, profile))

    append_field(rows, "DESIGN", "Display", summarize_display(lines))
    append_field(rows, "DESIGN", "Form Factor", summarize_simple_field(lines, ["Form Factor"], ["Dimensions (WxDxH)"], 3))
    append_field(rows, "DESIGN", "Dimensions (WxDxH)", summarize_dimensions(lines))
    append_field(rows, "DESIGN", "Weight", summarize_weight(lines))
    append_field(rows, "DESIGN", "Color", summarize_color(lines, profile))
    if profile == "Legion":
        append_field(rows, "DESIGN", "Chassis", summarize_simple_field(lines, ["Chassis**", "Chassis"], ["Bays"], 6))
    append_field(rows, "DESIGN", "Bays", summarize_bays(lines))
    append_field(rows, "DESIGN", "Expansion Slots", summarize_expansion_slots(lines))
    if profile == "Legion":
        append_field(
            rows,
            "DESIGN",
            "Cooling System (Fan & Cooler)",
            summarize_simple_field(lines, ["Cooling System (Fan & Cooler)***", "Cooling System (Fan & Cooler)"], ["System Lighting", "CONNECTIVITY"], 12),
        )

    append_field(rows, "CONNECTIVITY", "Ethernet", summarize_ethernet(lines, profile))
    append_field(rows, "CONNECTIVITY", "WLAN + Bluetooth", summarize_wlan(lines))
    append_field(rows, "CONNECTIVITY", "Front Ports", summarize_ports(lines, "Front Ports"))
    append_field(rows, "CONNECTIVITY", "Rear Ports", summarize_ports(lines, "Rear Ports"))
    append_field(rows, "CONNECTIVITY", "Optional Ports", summarize_ports(lines, "Optional Rear Ports", optional=True))
    append_field(rows, "CONNECTIVITY", "Top Ports", summarize_ports(lines, "Top Ports"))
    append_field(rows, "CONNECTIVITY", "Left Ports", summarize_ports(lines, "Left Ports"))
    append_field(rows, "CONNECTIVITY", "Right Ports", summarize_ports(lines, "Right Ports"))

    append_field(rows, "SECURITY & PRIVACY", "Security", summarize_security(lines, profile))
    append_field(rows, "MANAGEABILITY", "System Management", summarize_manageability(lines))
    append_field(rows, "SERVICE", "Base Warranty", summarize_base_warranty(lines))
    append_field(rows, "ENVIRONMENTAL", "Material", summarize_material(lines))
    append_field(rows, "CERTIFICATIONS", "Green Certifications", summarize_green_certifications(lines))
    append_field(rows, "CERTIFICATIONS", "Other Certifications", summarize_other_certifications(lines))

    return rows


def build_shortdesc(product_name: str, spec_text: str, profile: str) -> str:
    return rows_to_text(build_dt_rows(product_name, spec_text, profile))


def table_rows_for_excel(rows: list[list[str]]) -> list[list[str]]:
    return [["L1 Feature", "L2 Feature", "Short Spec"], *rows]


def save_generation_texts(results: Iterable[GenerationResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        suffix = "_error" if result.error else ""
        (out_dir / f"{result.product}{suffix}.txt").write_text(result.shortdesc_text, encoding="utf-8")


def write_manifest(results: list[GenerationResult], workbook_path: Path, workbook_layout: str) -> None:
    workbook_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "workbook": str(workbook_path),
                "generator": "rule_based_dt",
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
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Lenovo DT short specs with common DT rules and IdeaCentre/ThinkCentre/Legion profiles."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--spec-files", "--spec-pdfs", dest="spec_pdfs", nargs="+")
    source_group.add_argument("--spec-dir")
    parser.add_argument("--glob", default="*_Spec.PDF")
    parser.add_argument("--output-xlsx", required=True)
    parser.add_argument(
        "--workbook-layout",
        choices=["per_product", "single_sheet_summary"],
        default="single_sheet_summary",
    )
    parser.add_argument("--runtime-text-dir", default="analysis_output/runtime_spec_text_rule_based_dt")
    parser.add_argument("--generated-text-dir", default="analysis_output/generated_shortspec_batch_rule_based_dt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    workbook_path = Path(args.output_xlsx).resolve()
    runtime_text_dir = Path(args.runtime_text_dir).resolve()
    generated_text_dir = Path(args.generated_text_dir).resolve()

    products = load_product_specs(spec_paths, runtime_text_dir)
    results: list[GenerationResult] = []
    sheets: list[tuple[str, str | list[list[str]]]] = []

    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.profile}\t{product.source_path}")
        try:
            rows = build_dt_rows(product.product, product.spec_text, product.profile)
            text = rows_to_text(rows)
            results.append(
                GenerationResult(
                    product=product.product,
                    source_path=str(product.source_path),
                    mode=f"rule_based_dt:{product.profile}",
                    shortdesc_text=text,
                    usage=None,
                    response_id=None,
                )
            )
            sheets.append((product.display_name, table_rows_for_excel(rows)))
        except Exception as exc:
            text = f"ERROR\nProduct\n{product.product}\nDetails\n{exc}"
            results.append(
                GenerationResult(
                    product=product.product,
                    source_path=str(product.source_path),
                    mode="error",
                    shortdesc_text=text,
                    usage=None,
                    response_id=None,
                    error=str(exc),
                )
            )
            sheets.append((sanitize_sheet_name(product.display_name, set()), text))

    save_generation_texts(results, generated_text_dir)
    write_xlsx(workbook_path, sheets, workbook_layout=args.workbook_layout)
    write_manifest(results, workbook_path, args.workbook_layout)

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
