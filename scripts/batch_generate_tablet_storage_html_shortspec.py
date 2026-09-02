from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from batch_generate_shortspec_excel import collect_spec_paths, derive_display_name, derive_product_name, write_xlsx
from html_sdw_runner import (
    HTML_SOURCE_MARKER,
    HTML_STORAGE_SECTION_END_LABELS,
    HTML_TOP_LEVEL_SECTION_MAP,
    collect_html_paths,
    html_label_key,
    html_to_text,
    normalize_product_filename,
)


MAX_STORAGE_KEYS = {"max storage support", "storage support"}
STORAGE_FIELD_KEYS = {
    "max storage support",
    "storage support",
    "storage slot",
    "storage slots",
    "storage type",
    "storage controllers",
    "storage controller",
    "raid",
}
STORAGE_SECTION_STOP_KEYS = (
    set(HTML_STORAGE_SECTION_END_LABELS)
    | {value.replace(" ", "-") for value in HTML_STORAGE_SECTION_END_LABELS}
    | set(HTML_TOP_LEVEL_SECTION_MAP)
    | {HTML_SOURCE_MARKER.lower().strip("_"), "html source spec"}
)
CAPACITY_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:TB|GB)\b", flags=re.I)


@dataclass(frozen=True)
class TabletStorageOption:
    capacities: tuple[str, ...]
    family: str
    spec: str


@dataclass(frozen=True)
class TabletStorageResult:
    product_name: str
    marketing_name: str
    source_path: str
    storage_short_specs: list[str]
    source_max_storage_support: str
    status: str
    source_storage_section: str


def clean_line(value: str) -> str:
    value = value.replace("\ufeff", "")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = re.sub(r"^[\s•\-\u2013]+", "", value)
    value = re.sub(r"\s*•\s*$", "", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return value


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def split_bullet_fragments(value: str) -> list[str]:
    return [clean_line(part) for part in re.split(r"\s*•\s*", value) if clean_line(part)]


def extract_storage_section(spec_text: str) -> list[str]:
    lines = [clean_line(line) for line in spec_text.splitlines() if clean_line(line)]
    for index, line in enumerate(lines):
        if html_label_key(line) != "storage":
            continue

        section: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            key = html_label_key(candidate)
            if candidate == HTML_SOURCE_MARKER or key in STORAGE_SECTION_STOP_KEYS:
                break
            section.append(candidate)
            cursor += 1
        return section
    return []


def collect_max_storage_values(section: list[str]) -> list[str]:
    values: list[str] = []
    active = False
    for line in section:
        key = html_label_key(line)
        if key in MAX_STORAGE_KEYS:
            active = True
            continue
        if not active:
            continue
        if key in STORAGE_FIELD_KEYS or key in STORAGE_SECTION_STOP_KEYS or key in {"notes", "notes:"}:
            break
        values.extend(split_bullet_fragments(line))
    return values


def normalize_capacity(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def parse_storage_family(value: str) -> tuple[str, str] | None:
    ufs = re.search(r"\bUFS(?:\s+(?P<version>\d+(?:\.\d+)?))?\b", value, flags=re.I)
    if ufs:
        version = ufs.group("version")
        return "UFS", f"UFS {version}" if version else "UFS"

    emmc = re.search(r"\beMMC(?:\s+(?P<version>\d+(?:\.\d+)?))?\b", value, flags=re.I)
    if emmc:
        version = emmc.group("version")
        return "eMMC", f"eMMC {version}" if version else "eMMC"

    return None


def parse_systemboard_option(value: str) -> TabletStorageOption | None:
    if "systemboard" not in value.lower():
        return None
    family = parse_storage_family(value)
    if family is None:
        return None
    capacities = tuple(normalize_capacity(match.group(0)) for match in CAPACITY_RE.finditer(value))
    if not capacities:
        return None
    return TabletStorageOption(capacities=capacities, family=family[0], spec=family[1])


def render_systemboard_options(options: list[TabletStorageOption]) -> list[str]:
    family_order = unique_preserve(option.family for option in options)
    rendered: list[str] = []
    for family in family_order:
        family_options = [option for option in options if option.family.lower() == family.lower()]
        capacities = unique_preserve(capacity for option in family_options for capacity in option.capacities)
        specs = unique_preserve(option.spec for option in family_options)
        label = specs[0] if len(specs) == 1 else family
        rendered.append(f"{' / '.join(capacities)} {label}")
    return rendered


def render_card_value(value: str) -> str:
    value = re.sub(r"\s*\([^)]*\)", "", value)
    return clean_line(value)


def is_card_value(value: str) -> bool:
    lowered = value.lower()
    return "card" in lowered and "systemboard" not in lowered


def render_tablet_storage_values(values: list[str]) -> list[str]:
    systemboard_options: list[TabletStorageOption] = []
    card_values: list[str] = []

    for value in values:
        systemboard = parse_systemboard_option(value)
        if systemboard:
            systemboard_options.append(systemboard)
            continue
        if is_card_value(value):
            rendered_card = render_card_value(value)
            if rendered_card:
                card_values.append(rendered_card)

    return unique_preserve([*render_systemboard_options(systemboard_options), *card_values])


def build_tablet_storage_result(html_path: Path) -> TabletStorageResult:
    marketing_name, spec_text = html_to_text(html_path)
    product_name = normalize_product_filename(marketing_name)
    section = extract_storage_section(spec_text)
    values = collect_max_storage_values(section)
    rendered = render_tablet_storage_values(values)
    status = "OK" if rendered else "Storage not found"
    return TabletStorageResult(
        product_name=product_name,
        marketing_name=marketing_name,
        source_path=str(html_path),
        storage_short_specs=rendered,
        source_max_storage_support="\n".join(values),
        status=status,
        source_storage_section="\n".join(section),
    )


def build_tablet_storage_result_from_text(spec_path: Path) -> TabletStorageResult:
    spec_text = spec_path.read_text(encoding="utf-8-sig", errors="replace")
    product_name = derive_product_name(spec_path)
    marketing_name = derive_display_name(spec_path)
    section = extract_storage_section(spec_text)
    values = collect_max_storage_values(section)
    rendered = render_tablet_storage_values(values)
    status = "OK" if rendered else "Storage not found"
    return TabletStorageResult(
        product_name=product_name,
        marketing_name=marketing_name,
        source_path=str(spec_path),
        storage_short_specs=rendered,
        source_max_storage_support="\n".join(values),
        status=status,
        source_storage_section="\n".join(section),
    )


def storage_feature_rows(result: TabletStorageResult) -> list[list[str]]:
    rows = [["L1 Feature", "L2 Feature", "Short Spec"]]
    if result.status == "OK":
        rows.extend(["PERFORMANCE", "Storage", value] for value in result.storage_short_specs)
    else:
        rows.append(["ERROR", "Details", result.status])
    return rows


def write_manifest(
    results: list[TabletStorageResult],
    workbook_path: Path,
    workbook_layout: str,
    manifest_path: Path | None = None,
) -> None:
    target_path = manifest_path or workbook_path.with_suffix(".json")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(
            {
                "workbook": str(workbook_path),
                "generator": "tablet_storage_html_systemboard_card_rules",
                "product_line": "tablet",
                "source_format": "html",
                "workbook_layout": workbook_layout,
                "results": [asdict(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_result_texts(results: list[TabletStorageResult], generated_text_dir: Path) -> None:
    generated_text_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        (generated_text_dir / f"{result.product_name}.txt").write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Tablet Storage ShortSpec from HTML using systemboard/card-only rules."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--html-files", nargs="+")
    source_group.add_argument("--html-dir")
    source_group.add_argument("--spec-files", "--spec-pdfs", dest="spec_files", nargs="+")
    source_group.add_argument("--spec-dir")
    parser.add_argument("--glob", default="*.html")
    parser.add_argument(
        "--output-xlsx",
        default="analysis_output/tablet_storage_html_systemboard_card_summary.xlsx",
    )
    parser.add_argument(
        "--workbook-layout",
        choices=["per_product", "single_sheet_summary"],
        default="single_sheet_summary",
    )
    parser.add_argument(
        "--generated-text-dir",
        default="analysis_output/generated_tablet_storage_html_systemboard_card",
    )
    parser.add_argument("--manifest-path")
    parser.add_argument("--runtime-text-dir")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.html_dir or args.html_files:
        html_paths = collect_html_paths(args.html_dir, args.glob, args.html_files)
        results = [build_tablet_storage_result(path) for path in html_paths]
    else:
        spec_paths = collect_spec_paths(args.spec_files, args.spec_dir, args.glob)
        results = [build_tablet_storage_result_from_text(path) for path in spec_paths]
    workbook_path = Path(args.output_xlsx).resolve()
    write_xlsx(
        workbook_path,
        [(result.marketing_name, storage_feature_rows(result)) for result in results],
        workbook_layout=args.workbook_layout,
    )
    manifest_path = Path(args.manifest_path).resolve() if args.manifest_path else None
    write_manifest(results, workbook_path, args.workbook_layout, manifest_path)
    write_result_texts(results, Path(args.generated_text_dir).resolve())
    print(f"WORKBOOK\t{workbook_path}")
    print(f"PRODUCTS\t{len(results)}")
    print(f"OK\t{sum(1 for result in results if result.status == 'OK')}")


if __name__ == "__main__":
    main()
