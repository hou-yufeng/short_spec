from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

VENDOR_PDF_DEPS = Path(__file__).resolve().parent / "_wlan_pdf_deps"
if VENDOR_PDF_DEPS.exists():
    sys.path.insert(0, str(VENDOR_PDF_DEPS))

from batch_generate_shortspec_excel import (
    GenerationResult,
    ProductSpec,
    collect_spec_paths,
    derive_display_name,
    derive_product_name,
    extract_pdf_texts,
    normalize_text,
    save_generation_texts,
    write_xlsx,
)


@dataclass(frozen=True)
class WLANToolConfig:
    product_line: str
    generator_name: str
    runtime_text_dir: str
    generated_text_dir: str
    output_xlsx: str


@dataclass(frozen=True)
class WLANOption:
    source: str
    index: int
    brand_model: str
    wifi_generation: str
    wifi_rank: int
    bluetooth_version: str
    capability_score: int


WLAN_LABELS = {
    "WLAN + Bluetooth",
    "WLAN + Bluetooth[1]",
    "WLAN + Bluetooth**",
    "WLAN + Bluetooth**[1]",
    "Wireless LAN + Bluetooth",
    "Wireless LAN",
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
    "Storage",
    "Storage Support",
    "Storage Type",
    "Storage Controllers",
    "RAID",
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
    "WWAN*",
    "WWAN**",
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
    "Notes",
    "Notes:",
}

KNOWN_BRANDS = (
    "Intel",
    "Qualcomm",
    "MediaTek",
    "Realtek",
    "Killer",
    "Broadcom",
    "Marvell",
    "Rivet",
    "AMD",
)

NEGATIVE_VALUES = {"", "-", "/", "N/A", "TBD", "None", "No support", "Non-touch"}


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
        "\u2022": "",
        "庐": "",
        "鈩?": "",
        "閳?": "",
        "搴?": "",
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"\bTM\b", "", line)
    line = line.replace("Wifi", "Wi-Fi").replace("wifi", "Wi-Fi").replace("WiFi", "Wi-Fi")
    line = re.sub(r"\bWi\s*-\s*Fi\b", "Wi-Fi", line, flags=re.I)
    line = re.sub(r"\bBlue\s*tooth\b", "Bluetooth", line, flags=re.I)
    line = re.sub(r"\s+", " ", line).strip(" -")
    return line


def clean_output(value: str) -> str:
    value = clean_line(value)
    value = re.sub(r"\b(?:N/A|TBD|Non-touch)\b", "", value, flags=re.I)
    value = re.sub(r"\bTM\b", "", value)
    value = re.sub(r"\s+", " ", value).strip(" ,.;")
    return value


def label_key(line: str) -> str:
    line = clean_line(line)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"\*+$", "", line)
    line = re.sub(r"[^a-z0-9+&/(). -]+", "", line.lower())
    return re.sub(r"\s+", " ", line).strip()


WLAN_LABEL_KEYS = {label_key(label) for label in WLAN_LABELS}
STOP_LABEL_KEYS = {label_key(label) for label in STOP_LABELS}


def is_page_noise_line(line: str) -> bool:
    cleaned = clean_line(line)
    if not cleaned:
        return True
    lowered = cleaned.lower()
    token = label_key(cleaned)
    if cleaned in NEGATIVE_VALUES:
        return True
    if token in {"psref", "product specifications", "reference"}:
        return True
    if re.search(r"\b\d+\s+of\s+\d+\b", lowered):
        return True
    if re.match(
        r"^[A-Za-z][A-Za-z0-9 +_-]+-\s*(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
        cleaned,
        flags=re.I,
    ):
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


def is_stop_line(line: str) -> bool:
    key = label_key(line)
    if clean_line(line).upper() in TOP_LEVEL_SECTIONS:
        return True
    if key in WLAN_LABEL_KEYS:
        return False
    if key in STOP_LABEL_KEYS:
        return True
    return any(key.startswith(stop + " ") for stop in STOP_LABEL_KEYS if stop)


def strip_wlan_label_prefix(line: str) -> tuple[bool, str]:
    cleaned = clean_line(line)
    key = label_key(cleaned)
    if key in WLAN_LABEL_KEYS:
        return True, ""
    pattern = re.compile(
        r"^\s*(?:WLAN|Wireless LAN)\s*\+\s*Bluetooth(?:\*+)?(?:\s*\[[0-9,\s]+\])?\s*[:,-]?\s*(?P<rest>.+)$",
        flags=re.I,
    )
    match = pattern.match(cleaned)
    if match:
        return True, clean_line(match.group("rest"))
    return False, ""


def split_lines(text: str) -> list[str]:
    return [clean_line(line) for line in normalize_text(text).splitlines() if clean_line(line)]


def split_option_fragments(line: str) -> list[str]:
    raw = line.replace("\u2022", ";").replace("•", ";").replace("；", ";")
    parts = re.split(r"\s*;\s*", raw)
    return [clean_line(part).strip(" ,;") for part in parts if clean_line(part).strip(" ,;")]


def starts_new_option(line: str) -> bool:
    lowered = line.lower()
    if lowered.startswith("no wlan"):
        return True
    if re.match(r"^(?:wi-fi|802\.11)", lowered):
        return True
    return any(re.match(rf"^{re.escape(brand.lower())}\b", lowered) for brand in KNOWN_BRANDS)


def has_wifi_or_bt(line: str) -> bool:
    return bool(re.search(r"\bWi-Fi\b|802\.11|Bluetooth|\bBT\s*\d", line, flags=re.I))


def should_merge_continuation(previous: str, current: str) -> bool:
    if not previous:
        return False
    if starts_new_option(current) and "bluetooth" in previous.lower():
        return False
    lowered_current = current.lower()
    if current.startswith((")", "(")):
        return True
    if previous.endswith((",", "+", "/", "-", "(", "and", "or")):
        return True
    if lowered_current.startswith(("+ bluetooth", "bluetooth", "bt")) and "bluetooth" not in previous.lower():
        return True
    if "wi-fi" in previous.lower() and "bluetooth" not in previous.lower() and has_wifi_or_bt(current):
        return True
    if "802.11" in previous.lower() and "bluetooth" not in previous.lower() and has_wifi_or_bt(current):
        return True
    if lowered_current.startswith("intel vpro") and has_wifi_or_bt(previous):
        return True
    return False


def normalize_wlan_tokens(tokens: Iterable[str]) -> list[str]:
    fragments: list[str] = []
    for token in tokens:
        for fragment in split_option_fragments(token):
            if not fragment or is_page_noise_line(fragment):
                continue
            if label_key(fragment) in WLAN_LABEL_KEYS:
                continue
            fragments.append(fragment)

    merged: list[str] = []
    for fragment in fragments:
        if merged and should_merge_continuation(merged[-1], fragment):
            merged[-1] = clean_line(f"{merged[-1]} {fragment}").strip(" ,")
        else:
            merged.append(fragment)
    return merged


def extract_wlan_block(spec_text: str) -> list[str]:
    lines = split_lines(spec_text)
    captured: list[str] = []
    index = 0
    while index < len(lines):
        is_label, remainder = strip_wlan_label_prefix(lines[index])
        if not is_label:
            index += 1
            continue

        block: list[str] = []
        if remainder:
            block.append(remainder)
        cursor = index + 1
        while cursor < len(lines):
            line = lines[cursor]
            is_next_label, next_remainder = strip_wlan_label_prefix(line)
            if is_next_label:
                if next_remainder:
                    block.append(next_remainder)
                break
            if is_page_noise_line(line):
                cursor += 1
                continue
            if is_stop_line(line):
                break
            block.append(line)
            cursor += 1

        captured.extend(normalize_wlan_tokens(block))
        index = max(cursor, index + 1)

    return unique_preserve(captured)


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = clean_output(value)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def extract_bluetooth_version(value: str) -> str:
    hardware_ready = re.findall(
        r"(?:Bluetooth|BT)\s*([0-9]+(?:\.[0-9]+)?)\s*hardware\s+ready",
        value,
        flags=re.I,
    )
    if hardware_ready:
        return max(hardware_ready, key=version_key)

    versions = re.findall(r"(?:Bluetooth|BT)\s*([0-9]+(?:\.[0-9]+)?)", value, flags=re.I)
    if not versions:
        return ""
    return max(versions, key=version_key)


def extract_wifi_generation(value: str) -> tuple[str, int]:
    lowered = value.lower()
    commercial_patterns = [
        (r"\bwi-fi\s*7\b", "Wi-Fi 7", 5),
        (r"\bwi-fi\s*6e\b", "Wi-Fi 6E", 4),
        (r"\bwi-fi\s*6\b", "Wi-Fi 6", 3),
        (r"\bwi-fi\s*5\b", "Wi-Fi 5", 2),
        (r"\bwi-fi\s*4\b", "Wi-Fi 4", 1),
    ]
    for pattern, label, rank in commercial_patterns:
        if re.search(pattern, lowered, flags=re.I):
            return label, rank

    if re.search(r"\b802\.11be\b", lowered):
        return "Wi-Fi 7", 5
    if re.search(r"\b802\.11ax\b", lowered):
        if re.search(r"\b(?:6e|6\s*ghz)\b", lowered):
            return "Wi-Fi 6E", 4
        return "Wi-Fi 6", 3
    if re.search(r"\b802\.11(?:[abgn/,+ -]*ac|ac)\b", lowered):
        return "Wi-Fi 5", 2
    if re.search(r"\b802\.11n\b", lowered):
        return "Wi-Fi 4", 1
    return "", 0


def extract_brand_model(value: str) -> str:
    cleaned = clean_line(value)
    brand_start: int | None = None
    for brand in KNOWN_BRANDS:
        match = re.search(rf"\b{re.escape(brand)}\b", cleaned, flags=re.I)
        if match and (brand_start is None or match.start() < brand_start):
            brand_start = match.start()

    if brand_start is None:
        return ""
    if cleaned[:brand_start].strip().lower().startswith("wi-fi"):
        return ""

    segment = cleaned[brand_start:]
    segment = re.split(r"\s*(?:,|\+ Bluetooth|Bluetooth|802\.11)", segment, maxsplit=1, flags=re.I)[0]
    segment = re.sub(r"\b(?:Intel\s+)?vPro(?:\s+technology)?(?:\s+support)?\b", " ", segment, flags=re.I)
    segment = re.sub(r"\bNon[- ]?vPro\b", " ", segment, flags=re.I)
    segment = re.sub(r"\b(?:Dual Band|Tri[- ]?band|M\.?2\s+card|PCIe\s+card|CNVi)\b", " ", segment, flags=re.I)
    segment = re.sub(r"\b(?:1x1|2x2|3x3|4x4)\b", " ", segment, flags=re.I)
    segment = re.sub(r"\b(?:160|240|320)MHz\b", " ", segment, flags=re.I)
    segment = re.sub(r"\s+", " ", segment).strip(" ,;+")
    if not segment or segment.lower().startswith("wi-fi"):
        return ""
    return clean_output(segment)


def capability_score(value: str, brand_model: str, bluetooth_version: str) -> int:
    lowered = value.lower()
    score = 0
    if "320mhz" in lowered:
        score += 40
    elif "240mhz" in lowered:
        score += 30
    elif "160mhz" in lowered:
        score += 20
    if re.search(r"\b4x4\b", lowered):
        score += 8
    elif re.search(r"\b3x3\b", lowered):
        score += 6
    elif re.search(r"\b2x2\b", lowered):
        score += 4
    elif re.search(r"\b1x1\b", lowered):
        score += 1
    if brand_model:
        score += 10 + min(len(brand_model.split()), 10)
    if bluetooth_version:
        score += min(sum(version_key(bluetooth_version)), 20)
    return score


def channel_width_score(value: str) -> int:
    widths = [int(match) for match in re.findall(r"\b(160|240|320)MHz\b", value, flags=re.I)]
    return max(widths, default=0)


def stream_score(value: str) -> int:
    scores = {"1x1": 1, "2x2": 2, "3x3": 3, "4x4": 4}
    matched = [score for token, score in scores.items() if re.search(rf"\b{token}\b", value, flags=re.I)]
    return max(matched, default=0)


def technical_spec_key(option: WLANOption) -> tuple[int, int, int, tuple[int, ...]]:
    return (
        option.wifi_rank,
        channel_width_score(option.source),
        stream_score(option.source),
        version_key(option.bluetooth_version),
    )


def is_intel_option(option: WLANOption) -> bool:
    return bool(re.search(r"\bIntel\b", option.brand_model or option.source, flags=re.I))


def parse_wlan_option(value: str, index: int) -> WLANOption | None:
    value = clean_output(value)
    if not value:
        return None
    lowered = value.lower()
    if lowered.startswith("no wlan") or "no wlan and bluetooth" in lowered:
        return None
    if "subject to the regulatory requirements" in lowered:
        return None
    if "may operate at a lower version" in lowered:
        return None
    if lowered in {item.lower() for item in NEGATIVE_VALUES}:
        return None

    wifi_generation, wifi_rank = extract_wifi_generation(value)
    bluetooth_version = extract_bluetooth_version(value)
    if not wifi_generation:
        return None

    brand_model = extract_brand_model(value)
    return WLANOption(
        source=value,
        index=index,
        brand_model=brand_model,
        wifi_generation=wifi_generation,
        wifi_rank=wifi_rank,
        bluetooth_version=bluetooth_version,
        capability_score=capability_score(value, brand_model, bluetooth_version),
    )


def option_identity(option: WLANOption) -> tuple[str, str, str]:
    return (option.brand_model.lower(), option.wifi_generation.lower(), option.bluetooth_version)


def highest_spec_options(options: list[WLANOption]) -> list[WLANOption]:
    if not options:
        return []
    max_key = max(technical_spec_key(option) for option in options)
    return [option for option in options if technical_spec_key(option) == max_key]


def choose_best_option(options: list[WLANOption]) -> WLANOption | None:
    if not options:
        return None
    highest_options = highest_spec_options(options)
    intel_options = [option for option in highest_options if is_intel_option(option)]
    candidate_options = intel_options or highest_options
    return max(
        candidate_options,
        key=lambda option: (
            option.wifi_rank,
            option.capability_score,
            version_key(option.bluetooth_version),
            bool(option.brand_model),
            -option.index,
        ),
    )


def should_suppress_brand_model(options: list[WLANOption]) -> bool:
    highest_options = highest_spec_options(options)
    return len(highest_options) >= 2 and not any(is_intel_option(option) for option in highest_options)


def render_wlan_option(option: WLANOption, *, up_to: bool, include_brand_model: bool = True) -> str:
    pieces: list[str] = []
    if include_brand_model and option.brand_model:
        pieces.append(option.brand_model)
    if option.wifi_generation:
        pieces.append(option.wifi_generation)
    if option.bluetooth_version:
        pieces.append(f"Bluetooth {option.bluetooth_version}")

    rendered = ", ".join(pieces)
    rendered = re.sub(r"\b802\.11[a-z0-9/,+ -]*\b", "", rendered, flags=re.I)
    rendered = re.sub(r"\b(?:1x1|2x2|3x3|4x4|Dual Band|Tri[- ]?band|(?:160|240|320)MHz|M\.?2\s+card|PCIe\s+card|CNVi)\b", "", rendered, flags=re.I)
    rendered = re.sub(r"\b(?:Intel\s+)?vPro(?:\s+technology)?(?:\s+support)?\b", "", rendered, flags=re.I)
    rendered = clean_output(rendered)
    if up_to and rendered:
        rendered = f"Up to {rendered}"
    return rendered


def build_wlan_short_specs(spec_text: str) -> list[str]:
    block = extract_wlan_block(spec_text)
    parsed: list[WLANOption] = []
    for index, value in enumerate(block):
        option = parse_wlan_option(value, index)
        if option:
            parsed.append(option)

    unique_options: list[WLANOption] = []
    seen: set[tuple[str, str, str]] = set()
    for option in parsed:
        identity = option_identity(option)
        if identity in seen:
            continue
        seen.add(identity)
        unique_options.append(option)

    best = choose_best_option(unique_options)
    if not best:
        return []

    rendered = render_wlan_option(
        best,
        up_to=len(unique_options) >= 2,
        include_brand_model=not should_suppress_brand_model(unique_options),
    )
    if not rendered:
        return []
    if re.search(r"\b(?:N/A|TBD|Non-touch|TM|vPro|802\.11|1x1|2x2|3x3|4x4|Dual Band|M\.?2\s+card)\b|[™®]", rendered, flags=re.I):
        return []
    return [rendered]


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


def table_rows_for_excel(rows: list[list[str]]) -> list[list[str]]:
    return [["L1 Feature", "L2 Feature", "Short Spec"], *rows]


def build_rows(spec_text: str) -> list[list[str]]:
    return [["CONNECTIVITY", "WLAN + Bluetooth", value] for value in build_wlan_short_specs(spec_text)]


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pypdf is not installed and no cached WLAN text was available.") from exc

    reader = PdfReader(str(path))
    return normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))


def load_wlan_product_specs(paths: list[Path], runtime_text_dir: Path) -> list[ProductSpec]:
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
            manifest_path = runtime_text_dir.parent / "runtime_spec_text_wlan_manifest.json"
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


def write_manifest(results: list[GenerationResult], workbook_path: Path, workbook_layout: str, config: WLANToolConfig) -> None:
    workbook_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "workbook": str(workbook_path),
                "generator": config.generator_name,
                "product_line": config.product_line,
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


def parse_args(config: WLANToolConfig) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Generate WLAN-only Lenovo short specs for {config.product_line} spec files."
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


def run(config: WLANToolConfig) -> None:
    args = parse_args(config)
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    runtime_text_dir = Path(args.runtime_text_dir).resolve()
    generated_text_dir = Path(args.generated_text_dir).resolve()
    workbook_path = Path(args.output_xlsx).resolve()

    products = load_wlan_product_specs(spec_paths, runtime_text_dir)
    results: list[GenerationResult] = []
    sheets: list[tuple[str, str | list[list[str]]]] = []

    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.source_path}")
        try:
            rows = build_rows(product.spec_text)
            text = rows_to_text(rows)
            result = GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode=config.generator_name,
                shortdesc_text=text,
                usage=None,
                response_id=None,
            )
            sheets.append((product.display_name, table_rows_for_excel(rows)))
        except Exception as exc:
            text = f"ERROR\nProduct\n{product.product}\nDetails\n{type(exc).__name__}: {exc}"
            result = GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="error",
                shortdesc_text=text,
                usage=None,
                response_id=None,
                error=f"{type(exc).__name__}: {exc}",
            )
            sheets.append((product.display_name, text))
        results.append(result)

    save_generation_texts(results, generated_text_dir)
    write_xlsx(workbook_path, sheets, workbook_layout=args.workbook_layout)
    write_manifest(results, workbook_path, args.workbook_layout, config)

    failures = [result for result in results if result.error]
    print(f"WORKBOOK\t{workbook_path}")
    print(f"SHEETS\t{1 if args.workbook_layout == 'single_sheet_summary' else len(sheets)}")
    print(f"FAILURES\t{len(failures)}")
    if failures:
        for failure in failures:
            print(f"FAILED\t{failure.product}\t{failure.error}")
        raise SystemExit(1)
