from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

VENDOR_PDF_DEPS = Path(__file__).resolve().parent / "_display_pdf_deps"
if VENDOR_PDF_DEPS.exists():
    sys.path.insert(0, str(VENDOR_PDF_DEPS))

from batch_generate_shortspec_excel import (
    GenerationResult,
    collect_spec_paths,
    derive_display_name,
    derive_product_name,
    normalize_text,
    ProductSpec,
    save_generation_texts,
    write_xlsx,
    extract_pdf_texts,
)


DISPLAY_HEADER_TOKENS = {
    "(L/R/U/D)",
    "Angle",
    "Aspect",
    "Aspect Ratio",
    "Brightness",
    "Color",
    "Color Gamut",
    "Contrast",
    "Contrast Ratio",
    "Display",
    "Display**",
    "Features",
    "Gamut",
    "Key",
    "Key Features",
    "Models",
    "Rate",
    "Ratio",
    "Refresh",
    "Refresh Rate",
    "Resolution",
    "Size",
    "Surface",
    "Touch",
    "Type",
    "Viewing",
    "Viewing Angle",
    "Viewing Angle (L/R/U/D)",
}

DISPLAY_STOP_LABELS = {
    "Touchscreen",
    "Touchscreen**",
    "Screen-to-Body Ratio",
    "Multi-mode",
    "Input Device",
    "Pen",
    "Keyboard",
    "Mechanical",
    "Connectivity",
    "Security & Privacy",
    "Service",
    "Accessories",
    "Operating Requirements",
    "Certifications",
    "Notes",
    "Notes:",
}

NEGATIVE_VALUES = {"", "-", "/", "N/A", "TBD", "None", "No support", "Non-touch"}


@dataclass(frozen=True)
class DisplayToolConfig:
    product_line: str
    generator_name: str
    runtime_text_dir: str
    generated_text_dir: str
    output_xlsx: str


def clean_line(line: str) -> str:
    line = line.replace("\ufeff", "")
    line = line.replace("\x00", "")
    line = line.replace("\x07", "")
    line = line.replace("\x0c", "\n")
    line = line.replace("\u00a0", " ")
    line = line.replace("\u00ae", "")
    line = line.replace("\u2122", "")
    line = line.replace("庐", "")
    line = line.replace("鈩?", "")
    line = line.replace("鈩", "")
    line = line.replace("T脺V", "TUV")
    line = line.replace("T眉V", "TUV")
    line = line.replace("TÜV", "TUV")
    line = line.replace("掳", "°")
    line = line.replace("™", "")
    line = line.replace("®", "")
    line = re.sub(r"\bTM\b", "", line)
    line = re.sub(r"\[[0-9,\s]+\]", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def label_token(line: str) -> str:
    line = clean_line(line)
    line = re.sub(r"\*+$", "", line)
    line = re.sub(r"[^a-z0-9+&/() -]+", "", line.lower())
    return re.sub(r"\s+", " ", line).strip()


def is_display_header_line(line: str) -> bool:
    cleaned = clean_line(line)
    if not cleaned:
        return True
    if cleaned in DISPLAY_HEADER_TOKENS:
        return True
    token = label_token(cleaned)
    if token in {label_token(item) for item in DISPLAY_HEADER_TOKENS}:
        return True
    words = re.findall(r"[A-Za-z/()&+-]+", cleaned)
    if words and all(word in {w for item in DISPLAY_HEADER_TOKENS for w in item.split()} for word in words):
        return True
    return False


def is_noise_line(line: str) -> bool:
    cleaned = clean_line(line)
    lowered = cleaned.lower()
    if cleaned in NEGATIVE_VALUES:
        return True
    if is_display_header_line(cleaned):
        return True
    if re.match(r"^\d+ of \d+", lowered):
        return True
    if lowered.startswith(("feature with ", "please refer", "lenovo reserves", "the system ")):
        return True
    if lowered.startswith(("for more information", "for details", "actual ", "measured diagonally")):
        return True
    if "product specifications reference" in lowered:
        return True
    return False


def find_display_start(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if label_token(line) == "display":
            return index
    return None


def extract_display_block(spec_text: str) -> list[str]:
    raw_lines = [clean_line(line) for line in spec_text.splitlines()]
    lines = [line for line in raw_lines if line]
    start = find_display_start(lines)
    if start is None:
        return []

    stop_tokens = {label_token(label) for label in DISPLAY_STOP_LABELS}
    block: list[str] = []
    data_started = False
    for line in lines[start + 1 :]:
        token = label_token(line)
        if token in stop_tokens:
            break
        if re.match(r'^\d+(?:\.\d+)?"|^[0-9.]+\'\'', line):
            data_started = True
        if not data_started:
            if not is_noise_line(line):
                block.append(line)
            continue
        if clean_line(line) not in {"", "-", "/", "N/A", "TBD", "None", "No support"}:
            block.append(line)
    return normalize_display_tokens(block)


def normalize_display_tokens(tokens: Iterable[str]) -> list[str]:
    normalized = [clean_line(token) for token in tokens if clean_line(token)]
    merged: list[str] = []
    index = 0
    while index < len(normalized):
        token = normalized[index]

        while token.count("(") > token.count(")") and index + 1 < len(normalized):
            index += 1
            token = f"{token} {normalized[index]}".strip()

        while token.endswith("-") and index + 1 < len(normalized):
            index += 1
            token = f"{token}{normalized[index]}".strip()

        if re.fullmatch(r"\d+%", token) and index + 1 < len(normalized):
            next_token = normalized[index + 1]
            if re.match(r"^(?:NTSC|sRGB|DCI-P3|Adobe RGB)$", next_token, flags=re.I):
                index += 1
                token = f"{token} {next_token}".strip()

        token = token.replace("DCI- P3", "DCI-P3")
        token = token.replace("anti- glare", "anti-glare")
        token = token.replace("Anti- glare", "Anti-glare")
        token = token.replace("anti- reflection", "anti-reflection")
        token = token.replace("anti- smudge", "anti-smudge")
        token = token.replace("anti- fingerprint", "anti-fingerprint")
        token = token.replace("Non- touch", "Non-touch")
        token = token.replace("Multi- touch", "Multi-touch")
        token = token.replace("On- cell", "On-cell")
        token = token.replace("In- cell", "In-cell")
        token = token.replace("Add- on", "Add-on")
        token = token.replace("Paper- like", "Paper-like")
        token = token.replace("TUV, Low Blue Light", "TUV Low Blue Light")
        token = token.replace("Antiglare", "Anti-glare")
        token = re.sub(r"\s+", " ", token).strip()
        if token:
            merged.append(token)
        index += 1
    return merged


def group_display_offerings(tokens: list[str]) -> list[list[str]]:
    offerings: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        match = re.match(r'^(?P<size>\d+(?:\.\d+)?"|[0-9.]+\'\')\s*(?P<rest>.*)$', token)
        if match:
            if current:
                offerings.append(current)
            current = [match.group("size")]
            rest = match.group("rest").strip(" ,")
            if rest:
                current.append(rest)
            continue
        if current:
            current.append(token)
    if current:
        offerings.append(current)
    return offerings


def normalize_brightness(value: str) -> str:
    value = re.sub(r"(\d+)\s*nits\b", r"\1 nits", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip(" ,")


def clean_fragment(value: str) -> str:
    value = clean_line(value)
    value = re.sub(r"\b(?:N/A|TBD|Non-touch)\b", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" ,.;")
    return value


def strip_touch_terms(value: str) -> tuple[str, bool]:
    lowered = value.lower()
    touch = bool(re.search(r"\b(?:multi[- ]?touch|touch)\b", lowered)) and not bool(
        re.search(r"\bnon-?\s*touch\b", lowered)
    )
    value = re.sub(r"\bNon[- ]?touch\b", " ", value, flags=re.I)
    value = re.sub(r"\b(?:Multi[- ]?touch|On[- ]?cell\s*touch|Oncell\s*touch|In[- ]?cell\s*touch|Incell\s*touch)\b", " ", value, flags=re.I)
    value = re.sub(r"\b(?:Add[- ]?on\s*Film\s*touch|Addon\s*Film\s*touch|OGS|OGM|On[- ]?cell|Oncell|In[- ]?cell|Incell|Add[- ]?on Film|Addon Film|GF2)\b", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" ,")
    return value, touch


def extract_resolution(rest: str) -> tuple[str, str]:
    match = re.match(
        r"\s*(?P<resolution>(?:(?:HD\+?|FHD|FHD\+|QHD|QHD\+|UHD|WUXGA|WQXGA|WQUXGA|[0-9.]+K)\s*)?\(\d+x\d+\))\s*(?P<tail>.*)$",
        rest,
        flags=re.I,
    )
    if match:
        return clean_fragment(match.group("resolution")), match.group("tail").strip()

    match = re.match(
        r"\s*(?P<resolution>HD\+?|FHD\+?|QHD\+?|UHD|WUXGA|WQXGA|WQUXGA|[0-9.]+K)\s+(?P<tail>.*)$",
        rest,
        flags=re.I,
    )
    if match:
        return clean_fragment(match.group("resolution")), match.group("tail").strip()
    return "", rest


def remove_viewing_angle(value: str) -> str:
    value = re.sub(r"(?:\d{1,3}°\s*/\s*){3}\d{1,3}°", " ", value)
    value = re.sub(r"horizontal:\s*\+/?-?\s*\d{1,3}°?,\s*vertical:\s*\+/?-?\s*\d{1,3}°?", " ", value, flags=re.I)
    value = re.sub(r"\b\d{1,3}°\s*/\s*\d{1,3}°\b", " ", value)
    return re.sub(r"\s+", " ", value).strip(" ,")


def parse_display_offering(tokens: list[str]) -> str:
    if not tokens:
        return ""
    size = tokens[0]
    segment = " ".join(tokens[1:])
    segment = normalize_display_tokens([segment])[0] if segment else ""
    segment = re.sub(r"(\d+)\s*nits\b", r"\1 nits", segment, flags=re.I)
    segment = re.sub(r"\s+", " ", segment).strip()

    resolution, rest = extract_resolution(segment)
    rest, has_touch = strip_touch_terms(rest)

    brightness_matches = list(re.finditer(r"\d+\s*nits(?:\s*\([^)]+\))?", rest, flags=re.I))
    first_brightness = brightness_matches[0] if brightness_matches else None
    last_brightness = brightness_matches[-1] if brightness_matches else None

    type_text = ""
    if first_brightness:
        type_text = clean_fragment(rest[: first_brightness.start()])
    else:
        type_match = re.search(r"\b(?:LTPS,\s*)?(?:IPS|OLED|TN|VA|WVA|ADS|LCD|TFT)\b", rest, flags=re.I)
        if type_match:
            type_text = clean_fragment(type_match.group(0))

    brightness = ""
    if brightness_matches:
        brightness = " / ".join(normalize_brightness(match.group(0)) for match in brightness_matches)

    aspect_match = re.search(r"\b\d{1,2}:\d{1,2}\b", rest)
    surface = ""
    if last_brightness and aspect_match and aspect_match.start() > last_brightness.end():
        surface = clean_fragment(rest[last_brightness.end() : aspect_match.start()])
    elif last_brightness:
        tail = rest[last_brightness.end() :]
        surface_match = re.search(
            r"(Paper-like Anti-glare|Anti-glare(?:,\s*anti-reflection)?(?:,\s*anti-smudge)?|Anti-reflection|Anti-fingerprint|Glossy|Matte)",
            tail,
            flags=re.I,
        )
        if surface_match:
            surface = clean_fragment(surface_match.group(0))

    aspect = aspect_match.group(0) if aspect_match else ""
    gamut_values = re.findall(r"\d+%\s*(?:NTSC|sRGB|DCI-P3|Adobe RGB)", rest, flags=re.I)
    gamut = " / ".join(unique_preserve(clean_fragment(value) for value in gamut_values))
    refresh_values = re.findall(r"\d+\s*Hz", rest, flags=re.I)
    refresh = " / ".join(unique_preserve(clean_fragment(value) for value in refresh_values))

    tail_start = 0
    if refresh_values:
        refresh_iter = list(re.finditer(r"\d+\s*Hz", rest, flags=re.I))
        tail_start = refresh_iter[-1].end()
    elif gamut_values:
        gamut_iter = list(re.finditer(r"\d+%\s*(?:NTSC|sRGB|DCI-P3|Adobe RGB)", rest, flags=re.I))
        tail_start = gamut_iter[-1].end()
    elif aspect_match:
        tail_start = aspect_match.end()
    elif last_brightness:
        tail_start = last_brightness.end()

    key_feature = clean_fragment(remove_viewing_angle(rest[tail_start:])) if tail_start else ""
    key_feature = re.sub(r"^\d+(?:,\d+)?:1\s*", "", key_feature)
    key_feature = clean_fragment(key_feature)

    type_part = clean_fragment(type_text)
    if has_touch and type_part:
        type_part = f"{type_part} touch"
    elif has_touch:
        type_part = "touch"

    first_part = " ".join(part for part in [size, resolution, type_part] if part)
    parts = [first_part, brightness, surface, gamut, refresh, aspect, key_feature]
    rendered = ", ".join(part for part in (clean_fragment(part) for part in parts) if part and part not in NEGATIVE_VALUES)
    rendered = re.sub(r"\s+", " ", rendered).strip(" ,.")
    if re.search(r"\b(?:N/A|TBD)\b", rendered, flags=re.I):
        return ""
    return rendered


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def build_display_short_specs(spec_text: str) -> list[str]:
    block = extract_display_block(spec_text)
    offerings = group_display_offerings(block)
    rendered = [parse_display_offering(offering) for offering in offerings]
    return unique_preserve(value for value in rendered if value)


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
    return [["DESIGN", "Display", value] for value in build_display_short_specs(spec_text)]


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pypdf is not installed and no cached Display text was available.") from exc

    reader = PdfReader(str(path))
    return normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))


def load_display_product_specs(paths: list[Path], runtime_text_dir: Path) -> list[ProductSpec]:
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
            manifest_path = runtime_text_dir.parent / "runtime_spec_text_display_manifest.json"
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


def write_manifest(results: list[GenerationResult], workbook_path: Path, workbook_layout: str, config: DisplayToolConfig) -> None:
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


def parse_args(config: DisplayToolConfig) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Generate Display-only Lenovo short specs for {config.product_line} spec files."
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


def run(config: DisplayToolConfig) -> None:
    args = parse_args(config)
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    runtime_text_dir = Path(args.runtime_text_dir).resolve()
    generated_text_dir = Path(args.generated_text_dir).resolve()
    workbook_path = Path(args.output_xlsx).resolve()

    products = load_display_product_specs(spec_paths, runtime_text_dir)
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
