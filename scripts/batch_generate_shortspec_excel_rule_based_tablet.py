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
    save_generation_texts,
    write_xlsx,
)


TOP_LEVEL_SECTIONS = [
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "SECURITY & PRIVACY",
    "ACCESSORIES",
    "CERTIFICATIONS",
]

SPEC_TOP_LEVEL_SECTIONS = {
    "OVERVIEW",
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "SECURITY & PRIVACY",
    "SERVICE",
    "ACCESSORIES",
    "OPERATING REQUIREMENTS",
    "CERTIFICATIONS",
    "SOFTWARE",
}

NOISE_PREFIXES = (
    "notes:",
    "note:",
    "for latest",
    "for details",
    "for more compatible",
    "please visit",
    "the transfer speed",
    "actual results",
    "actual battery",
    "all battery life",
    "the maximum capacity",
    "the system dimensions",
    "the system weight",
    "measured diagonally",
    "ips (in-plane",
    "lenovo reserves",
)

NOISE_LINES = {
    "",
    "/",
    "-",
    "Notes",
    "Notes:",
    "Models",
    "Model",
    "No support",
    "None",
    "No base warranty",
    "No power adapter",
    "No pen bundled (purchase separately)",
    "No pen bundled",
    "No location service",
    "Product Specifications",
    "Reference",
    "PSREF",
}

DISPLAY_HEADER_TOKENS = {
    "Size",
    "Resolution",
    "Touch",
    "Type",
    "Brightness",
    "Surface",
    "Aspect",
    "Aspect Ratio",
    "Ratio",
    "Contrast",
    "Contrast Ratio",
    "Color",
    "Gamut",
    "Color Gamut",
    "Refresh",
    "Refresh Rate",
    "Viewing",
    "Angle",
    "Viewing Angle",
    "Key",
    "Features",
    "Key Features",
}


@dataclass
class ProductSpec:
    product: str
    display_name: str
    source_path: Path
    spec_text: str


def clean_line(line: str, *, keep_optional_star: bool = False) -> str:
    optional = "鈥?" in line or line.rstrip().endswith("*")
    line = normalize_text(line)
    optional = optional or "\u2022" in line
    replacements = {
        "\ufeff": "",
        "\xa0": " ",
        "聽": " ",
        "庐": "",
        "鈩?": "",
        "鈥?": "",
        "掳": "\u00b0",
        "脺": "\u00dc",
        "T\u810aV": "T\u00dcV",
        "Android™": "Android",
        "Wi-Fi®": "Wi-Fi",
        "Bluetooth®": "Bluetooth",
        "USB-C®": "USB-C",
        "Lenovo®": "Lenovo",
        "Qualcomm®": "Qualcomm",
        "Snapdragon®": "Snapdragon",
        "Adreno™": "Adreno",
        "Dolby Atmos®": "Dolby Atmos",
        "Corning®": "Corning",
        "Gorilla®": "Gorilla",
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    line = line.replace("\u2022", "")
    line = line.replace("\u00ae", "")
    line = line.replace("\u2122", "")
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    line = line.replace("T\u810aV", "T\u00dcV")
    line = line.replace("T脺V", "T\u00dcV")
    if keep_optional_star and optional and line and not line.endswith("*"):
        line += "*"
    return line


def split_lines(text: str) -> list[str]:
    return [clean_line(line) for line in normalize_text(text).splitlines() if clean_line(line)]


def label_token(line: str) -> str:
    line = clean_line(line)
    line = re.sub(r"\*+$", "", line)
    line = re.sub(r"[^a-z0-9+&/() -]+", "", line.lower())
    return re.sub(r"\s+", " ", line).strip()


def is_noise(line: str) -> bool:
    cleaned = clean_line(line)
    lowered = cleaned.lower()
    if cleaned in NOISE_LINES:
        return True
    if re.fullmatch(r"\[[0-9,\s]+\]", cleaned):
        return True
    if any(lowered.startswith(prefix) for prefix in NOISE_PREFIXES):
        return True
    if re.match(r"^\d+ of \d+", lowered):
        return True
    if "psref product specifications reference" in lowered:
        return True
    if re.match(r"^(Idea Tab|Legion Tab|Tab [A-Z0-9]|ThinkTab|Yoga Tab)", cleaned):
        if not any(keyword in lowered for keyword in ["pen", "keyboard", "case", "pack", "adapter"]):
            return True
    if cleaned == "Lenovo Tab":
        return True
    return False


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        upper = line.upper()
        if upper in SPEC_TOP_LEVEL_SECTIONS:
            current = upper
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = clean_line(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def find_label_index(lines: list[str], labels: Iterable[str], *, start: int = 0) -> int | None:
    wanted = {label_token(label) for label in labels}
    for index in range(start, len(lines)):
        if label_token(lines[index]) in wanted:
            return index
    return None


def slice_after_label(
    lines: list[str],
    labels: Iterable[str],
    stop_labels: Iterable[str],
    *,
    start: int = 0,
) -> list[str]:
    start_index = find_label_index(lines, labels, start=start)
    if start_index is None:
        return []

    stops = {label_token(label) for label in stop_labels}
    captured: list[str] = []
    for line in lines[start_index + 1 :]:
        token = label_token(line)
        if token in stops:
            break
        captured.append(line)
    return captured


def filtered_values(lines: Iterable[str], *, keep_optional_star: bool = False) -> list[str]:
    result: list[str] = []
    for raw in lines:
        value = clean_line(raw, keep_optional_star=keep_optional_star)
        lowered = value.lower()
        if is_noise(value):
            continue
        if lowered.startswith("feature with "):
            continue
        if lowered.startswith("no support") or lowered == "no":
            continue
        result.append(value)
    return unique_preserve(result)


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pypdf is not installed and no cached tablet text was available.") from exc

    reader = PdfReader(str(path))
    return normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))


def load_product_specs(paths: list[Path], runtime_text_dir: Path | None) -> list[ProductSpec]:
    pdf_paths = [path for path in paths if path.suffix.lower() == ".pdf"]
    cached_texts: dict[Path, str] = {}
    missing_pdf_paths: list[Path] = []

    if runtime_text_dir:
        for path in pdf_paths:
            cache_path = runtime_text_dir / f"{path.name}.txt"
            if cache_path.exists():
                cached_texts[path] = normalize_text(cache_path.read_text(encoding="utf-8-sig"))
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
            manifest_path = runtime_text_dir.parent / "runtime_spec_text_rule_based_tablet_manifest.json"
            extracted_texts = extract_pdf_texts(missing_pdf_paths, runtime_text_dir, manifest_path)

    products: list[ProductSpec] = []
    for path in paths:
        if path.suffix.lower() == ".pdf":
            text = cached_texts.get(path) or extracted_texts[path]
        else:
            text = normalize_text(path.read_text(encoding="utf-8-sig"))
        products.append(
            ProductSpec(
                product=derive_product_name(path),
                display_name=derive_display_name(path),
                source_path=path,
                spec_text=text,
            )
        )
    return products


def simplify_processor_name(value: str) -> str:
    value = clean_line(value)
    value = re.sub(r"\bProcessor Name\b|\bCores\b|\bMax Frequency\b|\bMemory Support\b|\bProcessor Graphics\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,")
    value = value.replace("ARM", "Arm")
    return value


def summarize_processor(perf: list[str]) -> list[str]:
    block = slice_after_label(perf, ["Processor Name"], ["Operating System"])
    if not block:
        block = slice_after_label(perf, ["Processor"], ["Operating System"], start=1)
    joined = simplify_processor_name(" ".join(filtered_values(block)))
    if not joined:
        return []

    joined = re.sub(r"\bLPDDR[0-9A-Za-zxX]+\b.*$", "", joined).strip()
    joined = re.sub(r"\b(?:Arm|ARM|Qualcomm|IMG|Mali|Adreno).{0,80}\bGPU\b.*$", "", joined).strip()
    core_match = re.search(r"\b(?:Octa|Quad)-core\b", joined, flags=re.I)
    if not core_match:
        return [joined]

    name = joined[: core_match.start()].strip(" ,")
    core = joined[core_match.start() :].strip(" ,")
    core = re.split(r"\s+(?:LPDDR|Arm|ARM|Qualcomm Adreno|Adreno|Mali|IMG|GPU)\b", core)[0].strip(" ,")
    core = re.sub(r"\s+", " ", core)
    if "@" in core and not name.lower().startswith("up to"):
        arch_match = re.match(
            r"((?:Octa|Quad)-core,?\s*(?:\d+x\s+(?:Kryo\s+\w+|Cortex-A\d+|A\d+|Gold|Silver|Prime|[A-Za-z0-9]+)(?:\s*\+\s*)?)+)",
            core,
            flags=re.I,
        )
        if arch_match:
            core = arch_match.group(1).strip(" +,")
        else:
            core = re.split(r"\s+[A-Za-z0-9-]+@\d", core)[0].strip(" ,")
    if not name:
        return [core]
    if name.lower().startswith("up to"):
        return [f"{name} ({core})"]
    if "mobile platform" in name.lower():
        return [name]
    return [f"{name}, {core}"]


def summarize_operating_system(perf: list[str]) -> list[str]:
    values = slice_after_label(perf, ["Operating System", "Operating System[1]"], ["Graphics", "Notes"])
    values = [value for value in filtered_values(values) if label_token(value) != "operating system"]
    return values[:1]


def summarize_graphics(perf: list[str]) -> list[str]:
    values = slice_after_label(perf, ["Graphics"], ["Memory"], start=0)
    values = [value for value in filtered_values(values) if label_token(value) != "graphics"]
    if not values:
        return []
    value = values[0].replace("Arm ", "ARM ")
    return [value]


def summarize_memory(perf: list[str]) -> list[str]:
    memory_values = slice_after_label(perf, ["Max Memory"], ["Memory Type", "Storage"])
    memory_type_values = slice_after_label(perf, ["Memory Type"], ["Storage"])
    memory_type = filtered_values(memory_type_values)[:1]
    mem_type = memory_type[0].replace("LPDDR4X", "LPDDR4x") if memory_type else ""

    out: list[str] = []
    for value in filtered_values(memory_values):
        lowered = value.lower()
        if "memory" not in lowered and not re.search(r"\b\d+\s*gb\b", lowered):
            continue
        match = re.search(r"((?:up to\s+)?\d+\s*GB)", value, flags=re.I)
        if not match:
            continue
        capacity = re.sub(r"\s+", "", match.group(1)).replace("Upto", "Up to")
        prefix = "Up to " if match.group(1).lower().startswith("up to") else ""
        capacity = re.sub(r"(?i)^upto", "", capacity)
        text = f"{prefix}{capacity}"
        if mem_type and mem_type.lower() not in text.lower():
            text = f"{text} {mem_type}"
        if "soldered" in lowered or "not upgradable" in lowered:
            text += ", soldered"
        out.append(text)
    return unique_preserve(out)


def storage_type_for(value: str) -> str:
    lowered = value.lower()
    if "ufs 4.0" in lowered:
        return "UFS 4.0"
    if "ufs 3.1" in lowered or "usf 3.1" in lowered:
        return "UFS 3.1"
    if "ufs 2.2" in lowered:
        return "UFS 2.2"
    if re.search(r"\bufs\b", lowered) or re.search(r"\busf\b", lowered):
        return "UFS"
    if "emmc 5.1" in lowered:
        return "eMMC 5.1"
    if "emmc" in lowered or "emcp" in lowered:
        return "eMMC 5.1"
    return ""


def summarize_storage(perf: list[str]) -> list[str]:
    block = slice_after_label(
        perf,
        ["Max Storage Support", "Max Storage Support**", "Storage Support"],
        ["Storage Type", "Removable Storage", "Multi-Media"],
    )
    values = filtered_values(block, keep_optional_star=False)
    grouped: dict[str, list[str]] = {}
    microsd: list[str] = []
    for value in values:
        if "microsd" in value.lower():
            match = re.search(r"supports up to\s+([0-9]+TB)", value, flags=re.I)
            microsd.append(f"MicroSD card, supports up to {match.group(1)}" if match else clean_line(value))
            continue
        capacities = re.findall(r"\b\d+\s*GB\b", value, flags=re.I)
        if not capacities:
            continue
        stype = storage_type_for(value)
        key = stype or "storage"
        grouped.setdefault(key, [])
        grouped[key].extend(re.sub(r"\s+", "", cap).upper().replace("GB", "GB") for cap in capacities)

    out: list[str] = []
    for stype, capacities in grouped.items():
        caps = unique_preserve(capacities)
        if stype.startswith("UFS"):
            out.append(f"{' / '.join(caps)} ({stype})")
        elif stype == "storage":
            out.append(" / ".join(caps))
        else:
            out.append(f"{' / '.join(caps)} {stype}")
    out.extend(unique_preserve(microsd))
    return unique_preserve(out)


def summarize_audio(perf: list[str]) -> list[str]:
    speaker_values = slice_after_label(perf, ["Speakers"], ["Microphone", "Camera", "Camera**", "Sensor", "Battery"])
    mic_values = slice_after_label(perf, ["Microphone"], ["Camera", "Camera**", "VoiceCall", "Sensor", "Battery"])
    out: list[str] = []
    for value in filtered_values(speaker_values):
        value = re.sub(r",?\s*optimized with\s+", ", ", value, flags=re.I)
        value = value.replace("Sound by", "sound by")
        value = re.sub(r"\s+", " ", value).strip(" ,")
        out.append(value)
    for value in filtered_values(mic_values):
        value = value.replace("Microphone", "microphone")
        value = value.replace("microphone Array", "microphone array")
        out.append(value)
    return unique_preserve(out)


def camera_groups(lines: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    for raw in lines:
        marker = "鈥?" in raw
        marker = marker or raw.strip() == "\u2022"
        value = clean_line(raw)
        if is_noise(value) or label_token(value) in {"camera", "camera"}:
            continue
        if marker and current:
            groups.append(current)
            current = []
            continue
        if value.lower().startswith("no "):
            continue
        current.append(value)
    if current:
        groups.append(current)
    return groups


def strip_camera_detail(value: str) -> str:
    value = re.sub(r",?\s*f/\d+(?:\.\d+)?", "", value, flags=re.I)
    value = re.sub(r",?\s*\d+(?:\.\d+)?\u00b0 FoV(?: \(field of view\))?", "", value, flags=re.I)
    value = re.sub(r",?\s*video recording[^,]+", "", value, flags=re.I)
    value = re.sub(r",?\s*fixed focus", "", value, flags=re.I)
    value = re.sub(r",?\s*face unlock(?: \(supported via OTA upgrade\))?", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip(" ,")


def summarize_camera(perf: list[str]) -> list[str]:
    block = slice_after_label(perf, ["Camera", "Camera**"], ["VoiceCall", "Sensor", "Battery"])
    out: list[str] = []
    for group in camera_groups(block):
        front = [strip_camera_detail(value) for value in group if value.lower().startswith("front")]
        rear = [strip_camera_detail(value) for value in group if value.lower().startswith("rear")]
        other = [strip_camera_detail(value) for value in group if not value.lower().startswith(("front", "rear"))]
        if front and rear:
            rear_text = rear[0].replace("Rear ", "rear ", 1)
            text = f"{front[0]} + {rear_text}"
            if len(rear) > 1:
                text += " / " + " / ".join(rear[1:])
            if other:
                text += ", " + ", ".join(other)
            out.append(text)
        else:
            out.extend(front + rear + other)
    return unique_preserve(out)


def summarize_sensors(perf: list[str]) -> list[str]:
    block = slice_after_label(perf, ["Sensor"], ["Battery"])
    out: list[str] = []
    skip_tokens = {"sensor", "sensors", "vibration motor"}
    for value in filtered_values(block, keep_optional_star=True):
        token = label_token(value)
        if token in skip_tokens:
            continue
        out.append(value.replace("Sar sensor", "SAR sensor"))
    return unique_preserve(out)


def summarize_battery(perf: list[str]) -> list[str]:
    battery_values = slice_after_label(perf, ["Battery"], ["Max Battery Life", "Charging Time", "Power Adapter"], start=0)
    life_values = slice_after_label(perf, ["Max Battery Life"], ["Notes", "Charging Time", "Power Adapter"])
    out: list[str] = []
    for value in filtered_values(battery_values):
        if re.search(r"\d+\s*mAh", value, flags=re.I):
            value = value.replace("Rechargeable Li-ion Battery", "battery")
            value = value.replace(", removable", "")
            value = re.sub(r"\s+", " ", value).strip(" ,")
            if not value.lower().endswith("battery"):
                value += " battery"
            out.append(value)
            break

    life_out: list[str] = []
    pending_label: str | None = None
    for value in filtered_values(life_values):
        lowered = value.lower()
        if lowered.endswith("models:") or lowered in {"5g models:", "wlan models:"}:
            pending_label = value.rstrip(":")
            continue
        if any(keyword in lowered for keyword in ["video", "youtube", "online meeting", "web browsing", "music playback"]):
            value = value.replace(":", " up to", 1) if re.search(r":\s*\d", value) else value
            if pending_label and not value.lower().startswith(pending_label.lower()):
                value = f"{pending_label}: {value}"
            life_out.append(value)
            pending_label = None
    out.extend(unique_preserve(life_out)[:4])
    return unique_preserve(out)


def summarize_charging_time(perf: list[str]) -> list[str]:
    values = slice_after_label(perf, ["Charging Time"], ["Power Adapter", "Notes"])
    return filtered_values(values)[:1]


def normalize_adapter(value: str) -> str:
    value = clean_line(value)
    value = re.sub(r",?\s*100-240V.*$", "", value, flags=re.I)
    value = value.replace("AC adapter", "adapter")
    value = value.replace("USB-C adapter", "USB-C adapter")
    match = re.search(r"\((\d+(?:\.\d+)?W)(?:\s*max)?\)\s+USB-C", value, flags=re.I)
    if match and value.lower().startswith(("10v/", "5v/", "5~", "11v/")):
        if "pd 3.0" not in value.lower() and "pps" not in value.lower():
            return f"{match.group(1)} USB-C adapter"
    return re.sub(r"\s+", " ", value).strip(" ,")


def summarize_power_adapter(perf: list[str]) -> list[str]:
    values = slice_after_label(perf, ["Power Adapter"], ["Notes", "DESIGN"])
    out = [normalize_adapter(value) for value in filtered_values(values)]
    out = [value for value in out if "no power adapter" not in value.lower() and not label_token(value).startswith("power adapter")]
    return unique_preserve(out)


def display_block(design: list[str]) -> str:
    values = slice_after_label(design, ["Display", "Display[1]"], ["Touchscreen", "Screen-to-Body Ratio", "Input Device", "Notes"])
    clean_values = [value for value in filtered_values(values) if value not in DISPLAY_HEADER_TOKENS]
    clean_values = [value for value in clean_values if label_token(value) not in {label_token(v) for v in DISPLAY_HEADER_TOKENS}]
    return " ".join(clean_values)


def display_segments(joined: str) -> list[str]:
    starts = [match.start() for match in re.finditer(r'\d+(?:\.\d+)?"', joined)]
    if not starts:
        return []
    starts.append(len(joined))
    segments: list[str] = []
    for index in range(len(starts) - 1):
        segment = joined[starts[index] : starts[index + 1]].strip(" ,")
        if segment:
            segments.append(segment)
    return segments


def summarize_display(design: list[str]) -> list[str]:
    joined = display_block(design)
    if not joined:
        return []
    out: list[str] = []
    for segment in display_segments(joined):
        size = re.search(r'\d+(?:\.\d+)?"', segment)
        resolution = re.search(r"(?:[A-Z0-9.]+K?|WUXGA|HD|FHD|2K|2\.5K|3K|3\.2K|3\.5K)?\s*\(\d+x\d+\)", segment, flags=re.I)
        brightness = re.findall(r"\d+nits(?:\s*\([^)]+\))?", segment, flags=re.I)
        gamut = re.findall(r"\d+%\s*(?:NTSC|DCI-P3|SRGB|sRGB)", segment, flags=re.I)
        refresh = re.findall(r"\d+Hz", segment, flags=re.I)
        aspect = re.search(r"\b\d{1,2}:\d{1,2}\b", segment)
        panel_parts: list[str] = []
        if "LTPS" in segment:
            panel_parts.append("LTPS")
        if re.search(r"\bIPS\b", segment):
            panel_parts.append("IPS")
        elif re.search(r"\bADS\b", segment):
            panel_parts.append("ADS")
        elif re.search(r"\bOLED\b", segment):
            panel_parts.append("OLED")
        surface = ""
        for candidate in ["Paper-like Anti-glare", "Anti-reflection", "Anti-fingerprint", "Glossy", "Matte"]:
            if candidate.lower() in segment.lower():
                surface = candidate
                break
        first_parts = [size.group(0) if size else ""]
        if resolution:
            first_parts.append(re.sub(r"\s+", " ", resolution.group(0)).strip())
        first_parts.extend(panel_parts)
        if surface:
            first_parts.append(surface)
        if aspect:
            first_parts.append(aspect.group(0))
        first_line = " ".join(part for part in first_parts if part)
        detail_parts: list[str] = []
        if brightness:
            detail_parts.append(" / ".join(unique_preserve(brightness)))
        detail_parts.append("touch")
        detail_parts.extend(unique_preserve(gamut))
        detail_parts.extend(unique_preserve(refresh))
        for feature in ["Dolby Vision", "HDR10", "Corning Gorilla Glass", "T\u00dcV Low Blue Light", "T\u00dcV Full Care Display"]:
            if feature.lower() in segment.lower():
                detail_parts.append(feature)
        if first_line:
            out.append(first_line)
        if detail_parts:
            out.append("- " + ", ".join(unique_preserve(detail_parts)))
    return unique_preserve(out)


def summarize_screen_to_body(design: list[str]) -> list[str]:
    values = slice_after_label(design, ["Screen-to-Body Ratio"], ["Notes", "Input Device", "Pen", "Mechanical"])
    return filtered_values(values)[:1]


def summarize_pen(design: list[str]) -> list[str]:
    values = slice_after_label(design, ["Pen", "Pen**"], ["Notes", "Mechanical"])
    cleaned = filtered_values(values)
    if cleaned:
        return [value for value in cleaned if "purchase separately" not in value.lower()][:2] or ["No pen (purchase separately)"]
    if any("no pen" in line.lower() for line in values):
        return ["No pen (purchase separately)"]
    return []


def summarize_dimensions(design: list[str]) -> list[str]:
    values = slice_after_label(design, ["Dimensions (WxDxH)", "Dimensions (WxDxH)[1]"], ["Weight"])
    return filtered_values(values)[:1]


def summarize_weight(design: list[str]) -> list[str]:
    values = slice_after_label(design, ["Weight", "Weight[2]"], ["Case Color", "Case Material"])
    return filtered_values(values)[:1]


def summarize_color(design: list[str]) -> list[str]:
    values = slice_after_label(design, ["Case Color", "Case Color**"], ["Case Material"])
    return filtered_values(values, keep_optional_star=False)


def summarize_case_material(design: list[str]) -> list[str]:
    values = slice_after_label(design, ["Case Material"], ["Buttons", "Notes"])
    return filtered_values(values)[:2]


def summarize_buttons(design: list[str]) -> list[str]:
    values = slice_after_label(design, ["Buttons"], ["Notes", "CONNECTIVITY"])
    return filtered_values(values)


def summarize_wlan(conn: list[str]) -> list[str]:
    values = slice_after_label(conn, ["WLAN + Bluetooth", "WLAN + Bluetooth[1]"], ["WWAN", "SIM Card", "Cellular Bands", "NFC", "Wi-Fi Direct"])
    cleaned = filtered_values(values)
    if not cleaned:
        return []
    value = " ".join(cleaned)
    standard = re.search(r"802\.11[a-z]+", value, flags=re.I)
    wifi = re.search(r"Wi-Fi\s*\dE?|Wi-Fi\s*7", value, flags=re.I)
    bt = re.search(r"Bluetooth\s*\d(?:\.\d)?", value, flags=re.I)
    pieces: list[str] = []
    if standard and wifi:
        pieces.append(f"{standard.group(0)} ({wifi.group(0)})")
    elif wifi:
        pieces.append(wifi.group(0))
    elif standard:
        pieces.append(standard.group(0))
    if bt:
        pieces.append(bt.group(0))
    return [", ".join(pieces)] if pieces else cleaned[:1]


def summarize_wwan(conn: list[str]) -> list[str]:
    values = slice_after_label(conn, ["WWAN"], ["SIM Card", "Cellular Bands", "NFC", "Wi-Fi Direct"])
    cleaned = [value for value in filtered_values(values, keep_optional_star=True) if "no support" not in value.lower()]
    if cleaned and not cleaned[0].endswith("*"):
        cleaned[0] += "*"
    return cleaned[:1]


def summarize_cellular_bands(conn: list[str]) -> list[str]:
    values = slice_after_label(conn, ["Cellular Bands"], ["NFC", "Wi-Fi Direct", "Wi-Fi Display", "Notes"])
    out: list[str] = []
    for value in filtered_values(values):
        if label_token(value) in {"models location", "sim card"}:
            continue
        out.append(value)
    return unique_preserve(out)


def summarize_nfc(conn: list[str]) -> list[str]:
    values = slice_after_label(conn, ["NFC"], ["Wi-Fi Direct", "Wi-Fi Display", "Location Services", "Ports"])
    return filtered_values(values)[:1]


def summarize_wifi_direct(conn: list[str]) -> list[str]:
    return filtered_values(slice_after_label(conn, ["Wi-Fi Direct"], ["Wi-Fi Display", "Location Services", "Ports"]))[:1]


def summarize_wifi_display(conn: list[str]) -> list[str]:
    return filtered_values(slice_after_label(conn, ["Wi-Fi Display"], ["Location Services", "Ports", "Notes"]))[:1]


def summarize_location_services(conn: list[str]) -> list[str]:
    values = slice_after_label(conn, ["Location Services", "Location Services**"], ["Notes", "Ports"])
    cleaned = filtered_values(values, keep_optional_star=True)
    out: list[str] = []
    for value in cleaned:
        token = label_token(value)
        if token in {"models location", "models"}:
            continue
        if "no location service" in value.lower() or "wlan models" in value.lower() and "no " in value.lower():
            continue
        out.append(value.replace("WWAN models ", "WWAN models only: "))
    return unique_preserve(out)


def summarize_ports(conn: list[str]) -> list[str]:
    values = slice_after_label(conn, ["Standard Ports", "Standard Ports[1]", "Ports"], ["Notes", "SECURITY & PRIVACY", "SERVICE"])
    out: list[str] = []
    for value in filtered_values(values):
        token = label_token(value)
        if token in {"standard ports", "ports"}:
            continue
        value = value.replace(" and ", " & ") if "charging and DP-Out" in value else value
        out.append(value)
    return unique_preserve(out)


def summarize_security(security: list[str], perf: list[str]) -> list[str]:
    out: list[str] = []
    fp = slice_after_label(security, ["Fingerprint Reader"], ["SERVICE", "Notes"])
    for value in filtered_values(fp):
        if "touch style" in value.lower():
            out.append("Touch style fingerprint reader")
            break
    if not out:
        camera_text = " ".join(slice_after_label(perf, ["Camera", "Camera**"], ["VoiceCall", "Sensor", "Battery"]))
        if "face unlock" in camera_text.lower():
            out.append("Face unlock supported")
    return unique_preserve(out)


def summarize_accessories(accessories: list[str]) -> list[str]:
    values = slice_after_label(accessories, ["Bundled Accessories", "Bundled Accessories***"], ["Notes", "OPERATING REQUIREMENTS", "CERTIFICATIONS"])
    return [
        value
        for value in filtered_values(values)
        if value.lower() != "none" and not label_token(value).startswith("bundled accessories")
    ]


def summarize_green_certifications(cert: list[str]) -> list[str]:
    values = slice_after_label(cert, ["Green Certifications"], ["Notes", "Other Certifications", "Dust and Water Resistant", "Mil-Spec Test"])
    out: list[str] = []
    for value in filtered_values(values, keep_optional_star=True):
        lowered = value.lower()
        if any(key in lowered for key in ["energy star", "energy rating", "erp lot", "rohs"]):
            value = re.sub(r"\. View details.*$", "", value)
            if "energy rating" in lowered and not value.endswith("*"):
                value += "*"
            out.append(value)
    return unique_preserve(out)


def summarize_other_certifications(cert: list[str]) -> list[str]:
    values = slice_after_label(cert, ["Other Certifications"], ["SOFTWARE"])
    out: list[str] = []
    for value in filtered_values(values, keep_optional_star=True):
        lowered = value.lower()
        token = label_token(value)
        if token in {"dust and water resistant", "mil-spec test"}:
            continue
        if "mil-std-810h" in lowered:
            out.append("MIL-STD-810H*")
            continue
        if "t\u00fcv" in lowered or "tuv" in lowered or "android enterprise" in lowered or "hi-res" in lowered:
            out.append(value)
    mil = slice_after_label(cert, ["Mil-Spec Test"], ["SOFTWARE", "Notes"])
    for value in filtered_values(mil, keep_optional_star=True):
        if "mil-std-810h" in value.lower():
            out.append("MIL-STD-810H*")
    return unique_preserve(out)


def add_field(rows: list[list[str]], l1: str, l2: str, values: Iterable[str]) -> None:
    for value in unique_preserve(values):
        if value:
            rows.append([l1, l2, value])


def build_table_rows(product_name: str, spec_text: str) -> list[list[str]]:
    del product_name
    lines = split_lines(spec_text)
    sections = split_sections(lines)
    perf = sections.get("PERFORMANCE", [])
    design = sections.get("DESIGN", [])
    conn = sections.get("CONNECTIVITY", [])
    security = sections.get("SECURITY & PRIVACY", [])
    accessories = sections.get("ACCESSORIES", [])
    cert = sections.get("CERTIFICATIONS", [])

    rows: list[list[str]] = [["L1 Feature", "L2 Feature", "Short Spec"]]

    add_field(rows, "PERFORMANCE", "Processor", summarize_processor(perf))
    add_field(rows, "PERFORMANCE", "Operating System", summarize_operating_system(perf))
    add_field(rows, "PERFORMANCE", "Graphics", summarize_graphics(perf))
    add_field(rows, "PERFORMANCE", "Memory", summarize_memory(perf))
    add_field(rows, "PERFORMANCE", "Storage", summarize_storage(perf))
    add_field(rows, "PERFORMANCE", "Audio", summarize_audio(perf))
    add_field(rows, "PERFORMANCE", "Camera", summarize_camera(perf))
    add_field(rows, "PERFORMANCE", "Sensors", summarize_sensors(perf))
    add_field(rows, "PERFORMANCE", "Battery", summarize_battery(perf))
    add_field(rows, "PERFORMANCE", "Charging Time", summarize_charging_time(perf))
    add_field(rows, "PERFORMANCE", "Power Adapter", summarize_power_adapter(perf))

    add_field(rows, "DESIGN", "Display", summarize_display(design))
    add_field(rows, "DESIGN", "Screen-to-Body Ratio", summarize_screen_to_body(design))
    add_field(rows, "DESIGN", "Pen", summarize_pen(design))
    add_field(rows, "DESIGN", "Dimensions (WxDxH)", summarize_dimensions(design))
    add_field(rows, "DESIGN", "Weight", summarize_weight(design))
    add_field(rows, "DESIGN", "Color", summarize_color(design))
    add_field(rows, "DESIGN", "Case Material", summarize_case_material(design))
    add_field(rows, "DESIGN", "Buttons", summarize_buttons(design))

    add_field(rows, "CONNECTIVITY", "WLAN + Bluetooth", summarize_wlan(conn))
    add_field(rows, "CONNECTIVITY", "WWAN", summarize_wwan(conn))
    add_field(rows, "CONNECTIVITY", "Cellular Bands", summarize_cellular_bands(conn))
    add_field(rows, "CONNECTIVITY", "NFC", summarize_nfc(conn))
    add_field(rows, "CONNECTIVITY", "Wi-Fi Direct", summarize_wifi_direct(conn))
    add_field(rows, "CONNECTIVITY", "Wi-Fi Display", summarize_wifi_display(conn))
    add_field(rows, "CONNECTIVITY", "Location Services", summarize_location_services(conn))
    add_field(rows, "CONNECTIVITY", "Ports", summarize_ports(conn))

    add_field(rows, "SECURITY & PRIVACY", "Security", summarize_security(security, perf))
    add_field(rows, "ACCESSORIES", "Bundled Accessories", summarize_accessories(accessories))
    add_field(rows, "CERTIFICATIONS", "Green Certifications", summarize_green_certifications(cert))
    add_field(rows, "CERTIFICATIONS", "Other Certifications", summarize_other_certifications(cert))

    return rows


def format_section_heading(name: str, heading_style: str) -> str:
    if heading_style == "legacy":
        return name.title().replace("And", "and")
    return name


def render_shortdesc_text(
    product_name: str,
    rows: list[list[str]],
    *,
    output_mode: str,
    heading_style: str,
) -> str:
    resolved_output_mode = "psref_wrapped" if output_mode == "auto" else output_mode
    lines: list[str] = []
    if resolved_output_mode == "psref_wrapped":
        lines.extend(["PSREF", "Product Specifications", "Reference", ""])
    elif heading_style == "legacy":
        lines.append(product_name.replace("_", " "))

    current_l1 = ""
    current_l2 = ""
    for row in rows[1:]:
        l1, l2, value = row
        if l1 != current_l1:
            lines.append(format_section_heading(l1, heading_style))
            current_l1 = l1
            current_l2 = ""
        if l2 != current_l2:
            lines.append(l2 if heading_style == "modern" else l2.title().replace("Wxdxh", "WxDxH"))
            current_l2 = l2
        lines.append(value)

    if resolved_output_mode == "psref_wrapped":
        lines.extend(
            [
                "",
                "Note:",
                "Feature with * is optional and only configured on selected models.",
                "The specifications on this page may not be available in all regions, and may be changed or updated without notice.",
            ]
        )
    return "\n".join(lines).strip() + "\n"


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
        "generator": "rule_based_tablet",
        "output_mode": output_mode,
        "heading_style": heading_style,
        "workbook_layout": workbook_layout,
        "results": [
            {
                "product": result.product,
                "source_path": result.source_path,
                "mode": result.mode,
                "response_id": result.response_id,
                "usage": result.usage,
                "error": result.error,
            }
            for result in results
        ],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Lenovo tablet short specs for multiple product spec files and save them to one Excel workbook."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--spec-files", "--spec-pdfs", dest="spec_pdfs", nargs="+")
    source_group.add_argument("--spec-dir")
    parser.add_argument("--glob", default="*_Spec.PDF")
    parser.add_argument("--output-xlsx", required=True)
    parser.add_argument(
        "--workbook-layout",
        choices=["per_product", "single_sheet_summary"],
        default="per_product",
    )
    parser.add_argument(
        "--output-mode",
        choices=["auto", "psref_wrapped", "content_only"],
        default="auto",
    )
    parser.add_argument(
        "--heading-style",
        choices=["modern", "legacy"],
        default="modern",
    )
    parser.add_argument(
        "--runtime-text-dir",
        default="analysis_output/runtime_spec_text_rule_based_tablet",
        help="Directory used to cache extracted spec text files.",
    )
    parser.add_argument(
        "--generated-text-dir",
        default="analysis_output/generated_shortspec_batch_rule_based_tablet",
        help="Directory used to save generated per-product text outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    runtime_text_dir = Path(args.runtime_text_dir).resolve() if args.runtime_text_dir else None
    generated_text_dir = Path(args.generated_text_dir).resolve()
    workbook_path = Path(args.output_xlsx).resolve()

    products = load_product_specs(spec_paths, runtime_text_dir)
    results: list[GenerationResult] = []
    sheets: list[tuple[str, str | list[list[str]]]] = []

    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.source_path}")
        try:
            rows = build_table_rows(product.display_name, product.spec_text)
            shortdesc_text = render_shortdesc_text(
                product.display_name,
                rows,
                output_mode=args.output_mode,
                heading_style=args.heading_style,
            )
            result = GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="rule_based_tablet",
                shortdesc_text=shortdesc_text,
                usage=None,
                response_id=None,
            )
            sheets.append((product.display_name, rows))
        except Exception as exc:  # pragma: no cover - batch tool should keep going per product.
            error_text = f"ERROR\nProduct\n{product.product}\nDetails\n{type(exc).__name__}: {exc}"
            result = GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="rule_based_tablet",
                shortdesc_text=error_text,
                usage=None,
                response_id=None,
                error=f"{type(exc).__name__}: {exc}",
            )
            sheets.append((product.display_name, error_text))
        results.append(result)

    save_generation_texts(results, generated_text_dir)
    write_xlsx(workbook_path, sheets, workbook_layout=args.workbook_layout)
    write_manifest(results, workbook_path, args.output_mode, args.heading_style, args.workbook_layout)

    failures = [result for result in results if result.error]
    print(f"DONE\tproducts={len(results)}\toutput={workbook_path}")
    if failures:
        for failure in failures:
            print(f"FAILED\t{failure.product}\t{failure.error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
