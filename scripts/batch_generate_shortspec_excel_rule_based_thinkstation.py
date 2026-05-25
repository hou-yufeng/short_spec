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
    "CERTIFICATIONS",
]

SPEC_TOP_LEVEL_SECTIONS = {
    "OVERVIEW",
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "SECURITY & PRIVACY",
    "MANAGEABILITY",
    "SERVICE",
    "ACCESSORIES",
    "OPERATING REQUIREMENTS",
    "CERTIFICATIONS",
    "SOFTWARE",
}

FIELD_LABELS = {
    "Processor",
    "Processor Family",
    "Processor Sockets",
    "Processor**",
    "AI (Artificial Intelligence)",
    "AI PC Category",
    "Operating System",
    "Operating System**",
    "Graphics",
    "Integrated Graphics",
    "Integrated Graphics**",
    "Discrete Graphics Support",
    "Discrete Graphics Support**",
    "Discrete Graphics Support[1]",
    "Discrete Graphics Offering",
    "Discrete Graphics Offering**",
    "Discrete Graphics Offering***",
    "Monitor Support",
    "Chipset",
    "Max Memory",
    "Memory Type",
    "Memory Type**",
    "Memory Slots",
    "Memory Protection",
    "Storage",
    "Max Storage Support",
    "Storage Support",
    "Storage Type",
    "Storage Type**",
    "Storage Type***",
    "Storage Controllers",
    "RAID",
    "Multi-Media",
    "Audio Chip",
    "Power Supply",
    "Power Supply**",
    "Mechanical",
    "Form Factor",
    "Dimensions (WxDxH)",
    "Weight",
    "Bays",
    "M.2 Slots",
    "Expansion Slots",
    "EOU",
    "Network",
    "WLAN + Bluetooth",
    "WLAN + Bluetooth**",
    "Onboard Ethernet",
    "Optional Ethernet",
    "Ports",
    "Front Ports",
    "Optional Front Ports",
    "Rear Ports",
    "Optional Rear Ports",
    "Security Chip",
    "Physical Locks",
    "Chassis Intrusion Switch",
    "BIOS Security",
    "System Management",
    "System Management**",
    "Diagnostic",
    "Green Certifications",
    "Other Certifications",
    "Mil-Spec Test",
    "ISV Certifications",
}

SECTION_STOP_LABELS = FIELD_LABELS | SPEC_TOP_LEVEL_SECTIONS | {"Notes", "Notes:"}


@dataclass(frozen=True)
class ProductSpec:
    product: str
    display_name: str
    source_path: Path
    spec_text: str


def strip_stars_and_notes(label: str) -> str:
    label = re.sub(r"\[[0-9,\s]+\]", "", label)
    return re.sub(r"\*+$", "", label).strip()


def label_key(line: str) -> str:
    line = clean_line(line)
    line = strip_stars_and_notes(line)
    line = re.sub(r"[^a-z0-9+&/(). -]+", "", line.lower())
    return re.sub(r"\s+", " ", line).strip()


def clean_line(line: str, *, keep_optional_star: bool = False) -> str:
    raw = line
    optional = bool(re.search(r"\(Optional\)|\*$", raw, flags=re.I))
    optional = optional or raw.rstrip().endswith("\u2022")
    line = normalize_text(line)
    replacements = {
        "\ufeff": "",
        "\u00a0": " ",
        "\x00": "-",
        "\u00ae": "",
        "\u2122": "",
        "\u2022": "",
        "聽": " ",
        "鈥?": "",
        "閳?": "",
        "庐": "",
        "鈩?": "",
        "漏": "",
        "脳": "x",
        "\u00d7": "x",
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"^\(Optional\)\s*", "", line, flags=re.I)
    line = re.sub(r"\s+", " ", line).strip(" -")
    line = line.replace("Wifi", "Wi-Fi").replace("wifi", "Wi-Fi")
    line = line.replace("Nvidia", "NVIDIA")
    line = re.sub(r"\bUSB-C\b", "USB-C", line)
    line = re.sub(r"\bPCIe\s+", "PCIe ", line)
    line = re.sub(r"\s+", " ", line).strip()
    if keep_optional_star and optional and line and not line.endswith("*"):
        line += "*"
    return line


FIELD_LABEL_KEYS = {label_key(label) for label in FIELD_LABELS}
SECTION_STOP_KEYS = {label_key(label) for label in SECTION_STOP_LABELS}


def split_lines(text: str) -> list[str]:
    return [clean_line(line) for line in normalize_text(text).splitlines() if clean_line(line)]


def is_section_heading(line: str) -> bool:
    return clean_line(line).upper() in SPEC_TOP_LEVEL_SECTIONS


def is_probable_page_noise(line: str) -> bool:
    line = clean_line(line)
    if not line:
        return True
    if line in {"PSREF", "Product Specifications", "Reference", "/", "-", "Notes", "Notes:"}:
        return True
    if re.search(r"\b\d+ of \d+\b", line) or re.match(r"^\d+ of \d+ThinkStation\b", line):
        return True
    if re.match(r"^ThinkStation\s+.+-\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b", line):
        return True
    if re.match(r"^ThinkStation\s+", line) and len(line.split()) <= 6:
        return True
    lowered = line.lower()
    if lowered.startswith(("notes:", "feature with ", "items with ", "the specifications on this page")):
        return True
    if lowered.startswith(("lenovo reserves", "please refer", "for more information", "for detailed information")):
        return True
    if lowered.startswith(("http://", "https://")):
        return True
    if "product specifications reference" in lowered:
        return True
    return False


def is_stop_line(line: str, stop_labels: set[str]) -> bool:
    if is_section_heading(line):
        return True
    key = label_key(line)
    return key in stop_labels


def find_label_index(lines: list[str], labels: Iterable[str], start: int = 0) -> int | None:
    normalized = {label_key(label) for label in labels}
    for index in range(start, len(lines)):
        if label_key(lines[index]) in normalized:
            return index
    return None


def slice_after_label(lines: list[str], labels: Iterable[str], stop_labels: Iterable[str]) -> list[str]:
    start = find_label_index(lines, labels)
    if start is None:
        return []
    stops = {label_key(label) for label in stop_labels}
    captured: list[str] = []
    for line in lines[start + 1 :]:
        if is_stop_line(line, stops):
            break
        captured.append(line)
    return captured


def normalize_value(value: str, *, keep_optional_star: bool = False) -> str:
    value = clean_line(value, keep_optional_star=keep_optional_star)
    value = value.replace("Intel Xeon", "Intel Xeon")
    value = value.replace("AMD Ryzen Threadripper", "AMD Ryzen Threadripper")
    value = value.replace("NVMe SSD", "NVMe SSD")
    value = value.replace("DisplayPort", "DisplayPort")
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return value


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


def merge_continuations(values: Iterable[str]) -> list[str]:
    merged: list[str] = []
    for raw in values:
        value = normalize_value(raw)
        if not value:
            continue
        if not merged:
            merged.append(value)
            continue
        previous = merged[-1]
        if previous.endswith("-"):
            merged[-1] = previous[:-1] + value
        elif value.startswith((")", "(BMC)", "(BMC")):
            merged[-1] = f"{previous} {value}".strip()
        elif previous.endswith((",", "/", "or", "and", "up", "RTX", "NVIDIA RTX")) or value.startswith("PRO "):
            merged[-1] = f"{previous} {value}".strip()
        else:
            merged.append(value)
    return merged


def filter_values(values: Iterable[str], *, keep_optional_star: bool = False) -> list[str]:
    result: list[str] = []
    for raw in merge_continuations(values):
        value = normalize_value(raw, keep_optional_star=keep_optional_star)
        lowered = value.lower()
        if not value:
            continue
        if is_probable_page_noise(value):
            continue
        if label_key(value) in FIELD_LABEL_KEYS:
            continue
        if lowered in {"none", "n/a", "no", "no support", "no bays"}:
            continue
        if lowered.startswith("no preload"):
            continue
        if lowered.startswith("no wlan"):
            continue
        if lowered.startswith(("the max memory", "system comes with", "the storage capacity")):
            continue
        result.append(value)
    return unique_preserve(result)


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pypdf is not installed and no cached ThinkStation text was available. "
            "Use --runtime-text-dir with cached text or run on a machine with Microsoft Word for PDF extraction."
        ) from exc

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
                cached_texts[path.resolve()] = normalize_text(cache_path.read_text(encoding="utf-8-sig"))
            else:
                missing_pdf_paths.append(path)
    else:
        missing_pdf_paths = pdf_paths

    extracted_texts: dict[Path, str] = {}
    if missing_pdf_paths:
        try:
            for path in missing_pdf_paths:
                extracted_texts[path.resolve()] = read_pdf_text(path)
                if runtime_text_dir:
                    runtime_text_dir.mkdir(parents=True, exist_ok=True)
                    (runtime_text_dir / f"{path.name}.txt").write_text(extracted_texts[path.resolve()], encoding="utf-8")
        except RuntimeError:
            if not runtime_text_dir:
                raise
            manifest_path = runtime_text_dir.parent / "runtime_spec_text_rule_based_thinkstation_manifest.json"
            extracted_texts = extract_pdf_texts(missing_pdf_paths, runtime_text_dir, manifest_path)

    products: list[ProductSpec] = []
    for path in paths:
        if path.suffix.lower() == ".pdf":
            text = cached_texts.get(path.resolve()) or extracted_texts[path.resolve()]
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


def summarize_processor(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["Processor Family", "Processor"], ["Processor**", "Processor Sockets", "AI (Artificial Intelligence)", "AI PC Category", "Operating System"]))
    if not values:
        start = find_label_index(lines, ["Processor"])
        if start is not None:
            captured: list[str] = []
            for line in lines[start + 1 :]:
                if label_key(line) == "processor":
                    continue
                if is_stop_line(line, {label_key(label) for label in ["AI (Artificial Intelligence)", "AI PC Category", "Operating System"]}):
                    break
                captured.append(line)
            values = filter_values(captured)
    if not values:
        return []
    value = values[0]
    value = re.sub(r"\s+Processor$", " processor", value)
    value = re.sub(r"\s+processor processor$", " processor", value, flags=re.I)
    if "Grace Blackwell Superchip" in value:
        value = value.replace("20-core Arm", "20 core Arm")
        return [value]
    if "Core Ultra" in value:
        value = re.split(r";\s*supports\b|,\s*supports\b", value, flags=re.I)[0]
        return [value]
    if "Xeon" in value:
        value = re.sub(r"\b\d+W\s+", "", value)
        value = re.split(r",\s*supports\b|;\s*supports\b", value, flags=re.I)[0]
        value = value.replace("5th or 4th Gen Intel Xeon Scalable processors", "5th Gen Intel Xeon Scalable family processors, Silver, Gold, or Platinum.")
        return [value.rstrip(".") if not value.endswith("Platinum.") else value]
    if "Threadripper PRO 9000 or 7000 WX Series" in value:
        value = value.replace("Threadripper PRO 9000 or 7000 WX Series", "Threadripper PRO 9000 WX Series")
        return [value]
    if "Threadripper PRO 5000 or 3000 Series" in value:
        value = "Up to one AMD Ryzen Threadripper PRO 5000WX Series"
        return [value]
    return [value]


def summarize_operating_system(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["Operating System**", "Operating System"], ["Graphics"]))
    result: list[str] = []
    for value in values:
        lowered = value.lower()
        if lowered.startswith("no preload"):
            continue
        if value.startswith("Red Hat Certified Hardware"):
            continue
        if value.startswith("Red Hat Enterprise Linux"):
            version = re.search(r"Red Hat Enterprise Linux\s+(\d+(?:\.\d+)?)", value)
            if version and version.group(1).startswith("10"):
                value = f"Red Hat Enterprise Linux {version.group(1)} (certified only)"
            else:
                value = "Red Hat Enterprise Linux (certified only)"
        result.append(value)
    return unique_preserve(result)


def clean_graphics_support(value: str) -> str:
    value = normalize_value(value)
    value = re.sub(r"\s+", " ", value).strip(" ,")
    value = value.replace("NVIDIA RTX PRO", "NVIDIA RTX PRO")
    return value


def discrete_offering_names(lines: list[str]) -> list[str]:
    block = filter_values(
        slice_after_label(
            lines,
            ["Discrete Graphics Offering***", "Discrete Graphics Offering**", "Discrete Graphics Offering"],
            ["Monitor Support", "Chipset"],
        )
    )
    result: list[str] = []
    for value in block:
        if not value.startswith("NVIDIA"):
            continue
        name_match = re.match(
            r"(NVIDIA (?:RTX PRO \d+ Blackwell(?: Max-Q)? Workstation Edition|RTX \d+ Ada Generation|RTX A\d+|T\d+|A\d+))",
            value,
        )
        if not name_match:
            continue
        name = name_match.group(1)
        memory = re.search(r"\b(\d+GB)\b", value)
        if name.startswith("NVIDIA RTX A"):
            name = name.replace("NVIDIA RTX A", "NVIDIA A")
        if name.startswith("NVIDIA RTX PRO") and "Blackwell" in name:
            result.append(name)
            continue
        if memory and not name.endswith(memory.group(1)) and re.search(r"(A1000|T1000|T400|A400)\b", name):
            name = f"{name} {memory.group(1)}"
        result.append(name)
    return unique_preserve(result)


def summarize_graphics(product_name: str, lines: list[str]) -> list[str]:
    if "PGX" in product_name:
        block = filter_values(slice_after_label(lines, ["Integrated Graphics", "Graphics"], ["Chipset"]))
        return block

    support = [
        clean_graphics_support(value)
        for value in filter_values(
            slice_after_label(lines, ["Discrete Graphics Support", "Discrete Graphics Support**"], ["Discrete Graphics Offering", "Discrete Graphics Offering**", "Discrete Graphics Offering***", "Monitor Support", "Chipset"])
        )
    ]
    if len(support) > 1:
        blackwell = [value for value in support if "Blackwell" in value]
        support = blackwell or support[-1:]

    integrated = filter_values(slice_after_label(lines, ["Integrated Graphics**", "Integrated Graphics"], ["Discrete Graphics Support", "Discrete Graphics Offering", "Monitor Support", "Chipset"]))
    integrated = [re.sub(r"^(Intel Graphics)$", r"\1 (integrated)", value) for value in integrated]
    integrated = [value if "(integrated)" in value.lower() else f"{value} (integrated)" for value in integrated if value.startswith(("Intel", "AMD"))]

    if "Tiny" in product_name:
        offerings = []
        for value in discrete_offering_names(lines):
            if re.search(r"\b(A400|A1000|T1000)\b", value):
                offerings.append(value)
        if offerings:
            return unique_preserve(integrated[:1] + offerings[:4])

    if support:
        return support
    offerings = discrete_offering_names(lines)
    return unique_preserve(integrated + offerings[:8])


def summarize_chipset(lines: list[str]) -> list[str]:
    return filter_values(slice_after_label(lines, ["Chipset"], ["Memory", "Max Memory"]))[:1]


def normalize_slot_count(value: str) -> str:
    value = normalize_value(value)
    value = re.sub(r",?\s*\d+\s+channels? capable.*$", "", value, flags=re.I)
    value = re.sub(r",?\s*(?:dual-|quad-|eight |sixteen |four |two )?channels? capable.*$", "", value, flags=re.I)
    value = re.sub(r"\bUDIMM\b|\bRDIMM\b|\bCUDIMM\b", "DIMM", value)
    value = re.sub(r"\bSO-DIMM\b", "SODIMM", value)
    value = re.sub(r"\s+", " ", value).strip(" ,")
    word_map = {
        "One": "one",
        "Two": "two",
        "Three": "three",
        "Four": "four",
        "Five": "five",
        "Six": "six",
        "Eight": "eight",
        "Sixteen": "sixteen",
    }
    for word, repl in word_map.items():
        value = re.sub(rf"^{word}\b", repl, value)
    return value


def summarize_memory(lines: list[str]) -> list[str]:
    max_values = filter_values(slice_after_label(lines, ["Max Memory"], ["Memory Type", "Memory Slots", "Storage"]))
    if not max_values:
        memory_type = filter_values(slice_after_label(lines, ["Memory Type", "Memory Type**"], ["Memory Slots", "Storage"]))
        return memory_type[:1]
    max_value = max_values[0]
    if "CSODIMM" in max_value:
        return [max_value]

    capacity = re.sub(r"\s*\([^)]*\)", "", max_value).strip(" ,")
    slot_values = filter_values(slice_after_label(lines, ["Memory Slots"], ["Memory Protection", "Storage", "Notes"]))
    slot_value = normalize_slot_count(slot_values[0]) if slot_values else ""
    type_values = filter_values(slice_after_label(lines, ["Memory Type", "Memory Type**"], ["Memory Slots", "Memory Protection", "Storage"]))
    type_hint = type_values[0] if type_values else ""

    if "DDR4" in type_hint and "ECC" in type_hint and re.search(r"\b8\s+DDR4", slot_value):
        return [f"{capacity} DDR4-3200 ECC, eight DIMMs"]
    if slot_value:
        return [f"{capacity}, {slot_value}"]
    return [capacity]


def summarize_storage(lines: list[str]) -> list[str]:
    values = filter_values(
        slice_after_label(
            lines,
            ["Max Storage Support", "Storage Support"],
            ["Storage Type", "Storage Type**", "Storage Type***", "Storage Controllers", "RAID", "Multi-Media", "Power Supply"],
        )
    )
    result: list[str] = []
    for value in values:
        value = value.replace("PCIe NVMe", "PCIe NVMe")
        value = re.sub(r"\bPCIe ([45])\.0 Performance SSD\b", r"Gen \1 Performance SSD", value)
        result.append(value)
    return unique_preserve(result[:12])


def normalize_power_supply(value: str) -> str:
    value = normalize_value(value)
    value = value.replace("Hot-swap", "Hot-swap")
    value = re.sub(r"\s+", " ", value)
    if value.lower() in {"power type efficiency key features"}:
        return ""
    adapter = re.match(r"^(\d+W)\s+(?:Adapter|Power Adapter|power adapter)\s+(\d+%)?", value, flags=re.I)
    if adapter:
        watts, efficiency = adapter.group(1), adapter.group(2) or ""
        return f"{watts} power adapter, {efficiency}".strip(" ,")
    fixed = re.match(r"^(\d+W)\s+(?:Fixed|Integrated)?\s*(\d+%)?\s*(.*)$", value, flags=re.I)
    if fixed and ("80 PLUS" in value or "Fixed" in value):
        watts, efficiency, rest = fixed.group(1), fixed.group(2) or "", fixed.group(3)
        prefix = "Up to two " if "up to two power supplies" in value.lower() else ""
        suffix = "80 PLUS Platinum qualified" if "80 PLUS Platinum" in rest else rest
        return f"{prefix}{watts} {efficiency} PSU, {suffix}".strip(" ,")
    if re.match(r"^\d+W\s+Adapter$", value, flags=re.I):
        return value.replace("Adapter", "adapter")
    return value


def summarize_power_supply(lines: list[str]) -> list[str]:
    block = filter_values(slice_after_label(lines, ["Power Supply**", "Power Supply"], ["DESIGN", "Mechanical", "Form Factor"]))
    if len(block) >= 2 and block[0].endswith("Hot") and block[1].startswith("swap"):
        block = [f"{block[0]}-{block[1]}"] + block[2:]
    result = [normalize_power_supply(value) for value in block]
    return unique_preserve(value for value in result if value)


def summarize_simple(lines: list[str], labels: Iterable[str], stops: Iterable[str], limit: int = 3) -> list[str]:
    return filter_values(slice_after_label(lines, labels, stops))[:limit]


def summarize_bays(lines: list[str]) -> list[str]:
    return filter_values(slice_after_label(lines, ["Bays"], ["M.2 Slots", "Expansion Slots", "EOU", "CONNECTIVITY"]))[:12]


def normalize_expansion_slot(value: str) -> str:
    value = normalize_value(value)
    value = re.sub(r",?\s*by (?:CPU|PCH|WRX90|C741).*$", "", value)
    value = re.sub(r",?\s*supports up to.*$", "", value)
    value = re.sub(r",?\s*(?:low profile|full height|full length|half length),?\s*$", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" ,")
    return value


def summarize_expansion_slots(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["Expansion Slots"], ["EOU", "Notes", "CONNECTIVITY", "Network"]))
    result = [normalize_expansion_slot(value) for value in values]
    return unique_preserve(value for value in result if value)[:18]


def summarize_ethernet(product_name: str, lines: list[str]) -> list[str]:
    onboard = filter_values(slice_after_label(lines, ["Onboard Ethernet"], ["Optional Ethernet", "Ports", "Front Ports", "Notes"]))
    optional = filter_values(slice_after_label(lines, ["Optional Ethernet"], ["Notes", "Ports", "Front Ports"]))
    if "PGX" in product_name and onboard:
        joined = " ".join(onboard)
        if "ConnectX" in joined or "10GbE" in joined:
            return ["10 GbE Ethernet, ConnectX-7 Smart NIC, 1x 10GbE RJ-45"]
    if not onboard:
        return []
    joined = " ".join(onboard)
    result: list[str] = []
    if re.search(r"\bTwo Ethernet\b", joined, flags=re.I):
        if "10GbE" in joined and "GbE" in joined:
            result.append("Two onboard Ethernet, GbE and 10GbE")
        elif "2.5GbE" in joined and "GbE" in joined:
            result.append("Two onboard Ethernet, GbE and 2.5GbE")
        else:
            result.append("Two onboard Ethernet")
    elif "10GbE" in joined or "10 Gigabit" in joined:
        result.append("One onboard 10Gb Ethernet")
    elif "2.5" in joined:
        result.append("One onboard 2.5Gb Ethernet")
    elif "Gigabit" in joined or "GbE" in joined:
        result.append("One onboard Gigabit Ethernet")
    else:
        result.append(onboard[0])
    if optional:
        result.append("Additional Ethernet options via PCIe adapter")
    return unique_preserve(result)


def summarize_wlan(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["WLAN + Bluetooth", "WLAN + Bluetooth**"], ["No WLAN and Bluetooth", "Onboard Ethernet", "Optional Ethernet"]))
    result: list[str] = []
    for value in values:
        bt = re.search(r"Bluetooth\s+(\d+(?:\.\d+)?)", value, flags=re.I)
        if "AX211" in value:
            result.append(f"Up to Intel Wi-Fi 6E AX211, Bluetooth {bt.group(1) if bt else ''}, vPro".strip(" ,"))
            continue
        if "AX210" in value:
            result.append(f"Up to Intel Wi-Fi 6E AX210, Bluetooth {bt.group(1) if bt else ''}, vPro".strip(" ,"))
            continue
        value = re.sub(r",?\s*Intel vPro technology support", "", value, flags=re.I)
        result.append(value)
    return unique_preserve(result[:3])


def summarize_ports(lines: list[str], primary_label: str, optional_label: str | None = None) -> list[str]:
    stop_by_label = {
        "Front Ports": ["Optional Front Ports", "Rear Ports", "Optional Rear Ports", "SECURITY & PRIVACY", "Security Chip"],
        "Rear Ports": ["Optional Rear Ports", "SECURITY & PRIVACY", "Security Chip", "Notes"],
    }
    values = filter_values(slice_after_label(lines, [primary_label], stop_by_label.get(primary_label, ["SECURITY & PRIVACY"])))
    if optional_label:
        values.extend(
            filter_values(
                slice_after_label(
                    lines,
                    [optional_label],
                    ["Rear Ports", "Optional Rear Ports", "SECURITY & PRIVACY", "Security Chip", "Notes"],
                ),
                keep_optional_star=True,
            )
        )
    result: list[str] = []
    for value in values:
        value = value.replace("USB4 20Gbps / USB 3.2 Gen 2x2", "USB4 20Gbps")
        value = value.replace("DisplayPort function", "DisplayPort function")
        value = re.sub(r"\s+", " ", value).strip(" ,")
        result.append(value)
    return unique_preserve(result[:24])


def normalize_security_value(value: str) -> str:
    optional = value.endswith("*")
    value = normalize_value(value)
    value = value.rstrip("*")
    lowered = value.lower()
    if "discrete tpm" in lowered:
        value = "Discrete TPM 2.0"
    elif "access panel lock kit with common key" in lowered:
        value = "Access Panel Lock Kit with Common Key"
    elif "access panel lock kit with unique key" in lowered:
        value = "Access Panel Lock Kit with Unique Key"
    elif "kensington" in lowered:
        value = "Kensington Security Slot, 3 x 7 mm"
    elif "padlock" in lowered:
        value = "Padlock Loop"
    elif "e-lock" in lowered:
        value = "E-lock"
    elif "cable lock" in lowered:
        value = "Cable lock"
    elif "chassis intrusion" in lowered:
        value = "Chassis intrusion switch"
    if optional and not value.endswith("*"):
        value += "*"
    return value


def summarize_security(lines: list[str]) -> list[str]:
    values: list[str] = []
    values.extend(filter_values(slice_after_label(lines, ["Security Chip"], ["Physical Locks", "Chassis Intrusion Switch", "BIOS Security", "System Management"]), keep_optional_star=True))
    values.extend(filter_values(slice_after_label(lines, ["Physical Locks"], ["Chassis Intrusion Switch", "BIOS Security", "System Management"]), keep_optional_star=True))
    chassis_values = [
        clean_line(value, keep_optional_star=True)
        for value in slice_after_label(lines, ["Chassis Intrusion Switch"], ["BIOS Security", "System Management", "Diagnostic", "SERVICE"])
        if clean_line(value) and not is_probable_page_noise(value)
    ]
    values.extend(chassis_values)
    result = [normalize_security_value(value) for value in values]
    return unique_preserve(value for value in result if value)[:10]


def normalize_management_value(value: str) -> str:
    optional = value.endswith("*")
    value = normalize_value(value).rstrip("*")
    if "IPMI 2.0-compliant baseboard management controller" in value:
        value = "IPMI 2.0-compliant baseboard management controller (BMC)"
    value = value.replace("Intel vPro Enterprise with Intel AMT", "Intel vPro Enterprise with Intel AMT")
    if optional and value and not value.endswith("*"):
        value += "*"
    return value


def summarize_system_management(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["System Management", "System Management**"], ["Diagnostic", "SERVICE", "CERTIFICATIONS", "Green Certifications", "Notes"]), keep_optional_star=True)
    result = []
    for value in values:
        lowered = value.lower()
        if lowered in {"system management"}:
            continue
        if lowered.startswith("non-vpro") or lowered.startswith("non vpro"):
            continue
        if "bmc" in lowered or "ipmi" in lowered or "vpro" in lowered or "amd pro manageability" in lowered:
            result.append(normalize_management_value(value))
    return unique_preserve(result[:5])


def normalize_green_cert(value: str) -> list[str]:
    optional = value.endswith("*")
    value = normalize_value(value).rstrip("*")
    result: list[str] = []
    patterns = [
        r"ENERGY STAR\s*\d+(?:\.\d+)?",
        r"EPEAT (?:Gold|Silver) Registered",
        r"ErP Lot \d+(?:/\d+)?",
        r"TCO Certified(?:, generation \d+|\s*\d+(?:\.\d+)?)?",
        r"RoHS compliant",
        r"GREENGUARD",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, value, flags=re.I):
            item = clean_line(match)
            if optional and not item.endswith("*"):
                item += "*"
            result.append(item)
    if result:
        return result
    if optional and value and not value.endswith("*"):
        value += "*"
    return [value] if value else []


def summarize_green_certifications(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["Green Certifications"], ["Other Certifications", "Mil-Spec Test", "ISV Certifications", "Notes"]), keep_optional_star=True)
    result: list[str] = []
    for value in values:
        result.extend(normalize_green_cert(value))
    return unique_preserve(result[:12])


def summarize_other_certifications(lines: list[str]) -> list[str]:
    values = []
    values.extend(filter_values(slice_after_label(lines, ["Other Certifications"], ["Mil-Spec Test", "ISV Certifications", "Notes"]), keep_optional_star=True))
    values.extend(filter_values(slice_after_label(lines, ["Mil-Spec Test"], ["ISV Certifications", "Notes"]), keep_optional_star=True))
    result: list[str] = []
    for value in values:
        if "MIL-STD" in value.upper():
            match = re.search(r"MIL-STD-\d+[A-Z]?", value, flags=re.I)
            item = match.group(0).upper() if match else value
            if "military test passed" in value.lower():
                item = f"{item} military test passed"
            result.append(item)
        elif "TUV" in value.upper() or "T\u00dcV" in value.upper():
            result.append(value)
    return unique_preserve(result[:8])


def summarize_isv_certifications(lines: list[str]) -> list[str]:
    values = filter_values(slice_after_label(lines, ["ISV Certifications"], ["Feature with", "Notes"]))
    result = []
    for value in values:
        if "ISV certifications" in value:
            result.append(value.replace("Lenovo Workstations", "Lenovo Workstations"))
        elif "isv-certifications" in value.lower() or "thinkworkstations.com" in value.lower():
            result.append("Please visit ISV certifications for Lenovo Workstations")
    return unique_preserve(result[:1])


def append_field(rows: list[list[str]], l1: str, l2: str, values: Iterable[str]) -> None:
    for value in unique_preserve(values):
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


def build_thinkstation_rows(product_name: str, spec_text: str) -> list[list[str]]:
    lines = split_lines(spec_text)
    rows: list[list[str]] = []

    append_field(rows, "PERFORMANCE", "Processor", summarize_processor(lines))
    append_field(rows, "PERFORMANCE", "Operating System", summarize_operating_system(lines))
    append_field(rows, "PERFORMANCE", "Graphics", summarize_graphics(product_name, lines))
    append_field(rows, "PERFORMANCE", "Chipset", summarize_chipset(lines))
    append_field(rows, "PERFORMANCE", "Memory", summarize_memory(lines))
    append_field(rows, "PERFORMANCE", "Storage", summarize_storage(lines))
    append_field(rows, "PERFORMANCE", "Power Supply", summarize_power_supply(lines))

    append_field(rows, "DESIGN", "Dimensions (WxDxH)", summarize_simple(lines, ["Dimensions (WxDxH)"], ["Weight"], 1))
    append_field(rows, "DESIGN", "Weight", summarize_simple(lines, ["Weight"], ["Bays", "M.2 Slots", "Expansion Slots", "EOU", "CONNECTIVITY"], 1))
    append_field(rows, "DESIGN", "Bays", summarize_bays(lines))
    append_field(rows, "DESIGN", "Expansion Slots", summarize_expansion_slots(lines))

    append_field(rows, "CONNECTIVITY", "Ethernet", summarize_ethernet(product_name, lines))
    append_field(rows, "CONNECTIVITY", "WLAN + Bluetooth", summarize_wlan(lines))
    append_field(rows, "CONNECTIVITY", "Front Ports", summarize_ports(lines, "Front Ports", "Optional Front Ports"))
    append_field(rows, "CONNECTIVITY", "Rear Ports", summarize_ports(lines, "Rear Ports", "Optional Rear Ports"))

    append_field(rows, "SECURITY & PRIVACY", "Security", summarize_security(lines))
    append_field(rows, "SECURITY & PRIVACY", "System Management", summarize_system_management(lines))

    append_field(rows, "CERTIFICATIONS", "ISV Certifications", summarize_isv_certifications(lines))
    append_field(rows, "CERTIFICATIONS", "Green Certifications", summarize_green_certifications(lines))
    append_field(rows, "CERTIFICATIONS", "Other Certifications", summarize_other_certifications(lines))

    return rows


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
                "generator": "rule_based_thinkstation",
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
        description="Generate Lenovo ThinkStation short specs from full PSREF spec files."
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
    parser.add_argument("--runtime-text-dir", default="analysis_output/runtime_spec_text_rule_based_thinkstation")
    parser.add_argument("--generated-text-dir", default="analysis_output/generated_shortspec_batch_rule_based_thinkstation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    workbook_path = Path(args.output_xlsx).resolve()
    runtime_text_dir = Path(args.runtime_text_dir).resolve() if args.runtime_text_dir else None
    generated_text_dir = Path(args.generated_text_dir).resolve()

    products = load_product_specs(spec_paths, runtime_text_dir)
    results: list[GenerationResult] = []
    sheets: list[tuple[str, str | list[list[str]]]] = []

    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.source_path}")
        try:
            rows = build_thinkstation_rows(product.product, product.spec_text)
            text = rows_to_text(rows)
            results.append(
                GenerationResult(
                    product=product.product,
                    source_path=str(product.source_path),
                    mode="rule_based_thinkstation",
                    shortdesc_text=text,
                    usage=None,
                    response_id=None,
                )
            )
            sheets.append((product.display_name, table_rows_for_excel(rows)))
        except Exception as exc:
            text = f"ERROR\nProduct\n{product.product}\nDetails\n{type(exc).__name__}: {exc}"
            results.append(
                GenerationResult(
                    product=product.product,
                    source_path=str(product.source_path),
                    mode="error",
                    shortdesc_text=text,
                    usage=None,
                    response_id=None,
                    error=f"{type(exc).__name__}: {exc}",
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
