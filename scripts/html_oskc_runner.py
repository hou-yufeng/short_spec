from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from batch_generate_shortspec_excel import derive_display_name, write_xlsx
from html_memory_common import MEMORY_FEATURE, generate_memory_short_spec
from html_all_runner import (
    FULL_CONFIGS,
    HTML_KEYBOARD_FEATURE,
    HTML_OTHER_CERTIFICATIONS_FEATURE,
    collect_html_keyboard_rows,
    collect_html_other_certification_rows,
    overlay_html_keyboard_rows,
    overlay_html_other_certification_rows,
    prepare_text_dirs,
    product_key,
    read_summary_rows,
    remove_l2_feature_rows,
    row_value,
    run_full_generator,
)
from html_sdw_runner import collect_html_paths, convert_html_sources, safe_rmtree


TARGET_L2_FEATURES = {
    MEMORY_FEATURE,
    "Operating System",
    "Special Features",
    HTML_KEYBOARD_FEATURE,
    HTML_OTHER_CERTIFICATIONS_FEATURE,
}
KEYBOARDLESS_CONFIGS = {"dt", "ts"}


def target_l2_features(config_key: str) -> set[str]:
    features = set(TARGET_L2_FEATURES)
    if config_key in KEYBOARDLESS_CONFIGS:
        features.discard(HTML_KEYBOARD_FEATURE)
    return features


def output_feature_scope(config_key: str) -> str:
    if config_key in KEYBOARDLESS_CONFIGS:
        return "Memory/OS/Special/Cert"
    return "Memory/Keyboard/OS/Special/Cert"


def with_note_column(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    output = [[*rows[0][:4], "Note"]]
    for row in rows[1:]:
        output.append([row_value(row, index) for index in range(5)])
    return output


def select_target_rows(rows: list[list[str]], config_key: str) -> list[list[str]]:
    if not rows:
        return rows
    features = target_l2_features(config_key)
    return [rows[0], *[row for row in rows[1:] if row_value(row, 2) in features]]


def collect_html_memory_rows(converted: list[dict[str, str]]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for item in converted:
        html_path = Path(item["source_html"])
        text_spec = Path(item["sdw_text_spec"])
        product = derive_display_name(text_spec)
        result = generate_memory_short_spec(
            html_path.read_text(encoding="utf-8-sig", errors="replace"),
            product,
        )
        if not result or not result.short_spec:
            continue
        rows[product_key(product)] = [product, "PERFORMANCE", MEMORY_FEATURE, result.short_spec, result.note]
    return rows


def overlay_html_memory_rows(full_rows: list[list[str]], memory_rows: dict[str, list[str]]) -> list[list[str]]:
    if not full_rows:
        return full_rows

    output: list[list[str]] = [full_rows[0]]
    inserted: set[str] = set()
    products_in_order: list[str] = []
    seen_products: set[str] = set()
    for row in full_rows[1:]:
        key = product_key(row_value(row, 0))
        if key and key not in seen_products:
            seen_products.add(key)
            products_in_order.append(key)

    for row in full_rows[1:]:
        product = row_value(row, 0)
        l2_feature = row_value(row, 2)
        key = product_key(product)
        replacement = memory_rows.get(key)

        if l2_feature == MEMORY_FEATURE:
            if replacement:
                output.append(replacement)
                inserted.add(key)
            continue

        output.append(row)

    for key in products_in_order:
        replacement = memory_rows.get(key)
        if replacement and key not in inserted:
            output.append(replacement)

    return output


def write_final_manifest(
    manifest_path: Path,
    output_xlsx: Path,
    converted: list[dict[str, str]],
    full_workbook: Path,
    config_key: str,
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "workbook": str(output_xlsx),
        "converted": converted,
        "config": config_key,
        "target_l2_features": sorted(target_l2_features(config_key)),
        "output_columns": ["Product", "L1 Feature", "L2 Feature", "Short Spec", "Note"],
        "note_column_rule_source": (
            "The Note column is the shared note field for feature-level note output. "
            "Current Memory Type notes are written to this Note column and are not appended to the Memory Short Spec cell. "
            "Future feature note outputs should use the same column."
        ),
        "full_rule_source": "Latest HTML full ShortSpec route: HTML source converted to text, then product-line full rule-based generator",
        "memory_rule_source": (
            "HTML div[specstructure='Memory'] rule using Max Memory, Memory Slots, and Memory Type. "
            "If Memory Slots does not mention systemboard/soldered, output first Memory Slots segment plus full Max Memory. "
            "If Memory Slots is systemboard/soldered only, output the highest Max Memory branch and a separate Memory speed up to line unless Max Memory already contains a memory type. "
            "If Memory Slots has both systemboard/soldered and slots, output the highest soldered/not-upgradable branch with matching Memory Type speed when needed, plus the highest non-soldered branch with matched slot text. "
            "Soldered output ends with not upgradable. ThinkStation uses Max Memory directly. "
            "Memory Type notes are emitted in the shared Note column, not appended to the Memory Short Spec cell."
        ),
        "keyboard_rule_source": (
            "HTML Keyboard and Keyboard Backlight feature override for Commercial, Consumer, SMB, and Tablet; "
            "these mobile product lines extract row count, multimedia Fn keys, spill-resistant, numeric keypad, and Chrome keyboard from Keyboard values unless none are present; "
            "when multiple positive Keyboard options produce the same extracted value, each option emits that extracted value followed by its differing non-common parts; "
            "DT and ThinkStation omit Keyboard from this MKOSC output; Keyboard Backlight uses direct positive values joined by ' / ', with only the last value retaining 'backlight'; "
            "None/No options are omitted and mark all remaining output options with '*'; model prefixes and parenthesized text are removed"
        ),
        "other_certifications_rule_source": (
            "HTML div[specstructure='Other Certifications'] feature values for non-ThinkStation; "
            "Other Certifications feature values are emitted before Mil-Spec Test values; registered/trademark symbols are removed; "
            "Mil-Spec Test value 'Work in progress' is ignored; omitted when the HTML div tag is absent; omitted for ThinkStation"
        ),
        "full_workbook": str(full_workbook),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run HTML-source ShortSpec generation for only Operating System, "
            "Special Features, Memory, Keyboard, and Other Certifications."
        )
    )
    parser.add_argument("--config", required=True, choices=sorted(FULL_CONFIGS), help="Product-line configuration key.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-dir", help="Directory containing source HTML files.")
    source_group.add_argument("--html-files", nargs="+", help="One or more source HTML files.")
    parser.add_argument("--glob", default="*.html", help="Glob used with --source-dir. Default: *.html")
    parser.add_argument("--output-xlsx", required=True, help="Final Excel workbook path.")
    parser.add_argument(
        "--work-dir",
        help="Directory for manifests, temporary converted specs, and intermediate workbooks. Default: _work next to the output workbook.",
    )
    parser.add_argument(
        "--workbook-layout",
        choices=["single_sheet_summary"],
        default="single_sheet_summary",
        help="The deliverable writes one summary worksheet.",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary converted text and intermediate workbooks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scripts_dir = Path(__file__).resolve().parent
    output_xlsx = Path(args.output_xlsx).resolve()
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work_dir).resolve() if args.work_dir else output_xlsx.parent / "_work"
    work_root.mkdir(parents=True, exist_ok=True)
    temp_root = work_root / "analysis_output" / f"html_oskc_tmp_{os.getpid()}_{int(time.time())}"
    sdw_text_dir = temp_root / "sdw_text"
    full_text_dir = temp_root / "full_text"
    full_workbook = temp_root / "full.xlsx"
    final_manifest = work_root / "manifests" / f"{output_xlsx.stem}.json"

    html_paths = collect_html_paths(args.source_dir, args.glob, args.html_files)
    print(f"{FULL_CONFIGS[args.config]['title']} - {output_feature_scope(args.config)} ShortSpec")
    print(f"HTML files: {len(html_paths)}")
    print(f"Output: {output_xlsx}")

    converted = convert_html_sources(html_paths, sdw_text_dir)
    converted = prepare_text_dirs(converted, sdw_text_dir, full_text_dir)
    (temp_root / "html_conversion_manifest.json").write_text(
        json.dumps({"converted": converted}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        run_full_generator(scripts_dir, args.config, full_text_dir, full_workbook, args.workbook_layout, work_root)

        full_rows = read_summary_rows(full_workbook)
        merged_rows = overlay_html_memory_rows(
            full_rows,
            collect_html_memory_rows(converted),
        )
        if args.config not in KEYBOARDLESS_CONFIGS:
            merged_rows = overlay_html_keyboard_rows(
                merged_rows,
                collect_html_keyboard_rows(converted, args.config),
            )
        else:
            merged_rows = remove_l2_feature_rows(merged_rows, HTML_KEYBOARD_FEATURE)
        if args.config != "ts":
            merged_rows = overlay_html_other_certification_rows(
                merged_rows,
                collect_html_other_certification_rows(converted),
            )
        else:
            merged_rows = remove_l2_feature_rows(merged_rows, HTML_OTHER_CERTIFICATIONS_FEATURE)
        final_rows = with_note_column(select_target_rows(merged_rows, args.config))

        write_xlsx(output_xlsx, [("All Products", final_rows)], workbook_layout="per_product")
        write_final_manifest(final_manifest, output_xlsx, converted, full_workbook, args.config)
        print(f"WORKBOOK\t{output_xlsx}")
        print("SHEETS\t1")
    finally:
        if not args.keep_temp:
            safe_rmtree(temp_root, work_root)
            analysis_dir = work_root / "analysis_output"
            try:
                analysis_dir.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    main()
