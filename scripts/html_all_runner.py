from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

from batch_generate_shortspec_excel import L2_FEATURES, TOP_LEVEL_FEATURES, derive_display_name, write_xlsx
from html_sdw_runner import BLOCK_TAGS, CONFIGS as SDW_CONFIGS, SKIP_TAGS
from html_sdw_runner import HTML_SOURCE_MARKER, attr_map, class_tokens, collect_html_paths, convert_html_sources, has_display_none, html_label_key, safe_rmtree
from merge_feature_workbooks import normalize_short_spec_rows, read_workbook_sheets


FULL_CONFIGS: dict[str, dict[str, object]] = {
    "com": {
        "title": "Lenovo Commercial Laptop HTML Full ShortSpec",
        "script": "batch_generate_shortspec_excel_rule_based.py",
        "runtime_dir": "runtime_html_all_full_com",
        "generated_dir": "generated_html_all_full_com",
        "extra_args": ["--output-mode", "auto", "--heading-style", "modern"],
    },
    "con": {
        "title": "Lenovo Consumer Laptop HTML Full ShortSpec",
        "script": "batch_generate_shortspec_excel_rule_based_consumer.py",
        "runtime_dir": "runtime_html_all_full_con",
        "generated_dir": "generated_html_all_full_con",
        "extra_args": ["--output-mode", "auto", "--heading-style", "modern"],
    },
    "smb": {
        "title": "Lenovo SMB Laptop HTML Full ShortSpec",
        "script": "batch_generate_shortspec_excel_rule_based_smb.py",
        "runtime_dir": "runtime_html_all_full_smb",
        "generated_dir": "generated_html_all_full_smb",
        "extra_args": ["--output-mode", "auto", "--heading-style", "modern"],
    },
    "tab": {
        "title": "Lenovo Tablet HTML Full ShortSpec",
        "script": "batch_generate_shortspec_excel_rule_based_tablet.py",
        "runtime_dir": "runtime_html_all_full_tab",
        "generated_dir": "generated_html_all_full_tab",
        "extra_args": [],
    },
    "dt": {
        "title": "Lenovo Desktop HTML Full ShortSpec",
        "script": "batch_generate_shortspec_excel_rule_based_dt.py",
        "runtime_dir": "runtime_html_all_full_dt",
        "generated_dir": "generated_html_all_full_dt",
        "extra_args": [],
    },
    "ts": {
        "title": "Lenovo ThinkStation HTML Full ShortSpec",
        "script": "batch_generate_shortspec_excel_rule_based_thinkstation.py",
        "runtime_dir": "runtime_html_all_full_ts",
        "generated_dir": "generated_html_all_full_ts",
        "extra_args": [],
    },
}

SDW_L2_FEATURES = {"Storage", "Display", "WLAN + Bluetooth"}
HTML_CASE_MATERIAL_FEATURE = "Case Material"
HTML_KEYBOARD_FEATURE = "Keyboard"
HTML_KEYBOARD_BACKLIGHT_FEATURE = "Keyboard Backlight"
HTML_OTHER_CERTIFICATIONS_FEATURE = "Other Certifications"
HTML_MIL_SPEC_FEATURE = "Mil-Spec Test"
HTML_OTHER_CERTIFICATIONS_SPEC_KEY = html_label_key(HTML_OTHER_CERTIFICATIONS_FEATURE)
MOBILE_KEYBOARD_CONFIGS = {"com", "con", "smb", "tab"}
PRODUCT_RULE_PACKAGES = {
    "com": "commercial_laptop",
    "con": "consumer_laptop",
    "smb": "smb_laptop",
    "tab": "tablet",
    "dt": "desktop",
    "ts": "thinkstation",
}


def product_rule_module(config_key: str, feature: str):
    return importlib.import_module(f"html_product_rules.{PRODUCT_RULE_PACKAGES[config_key]}.{feature}")
HTML_CASE_MATERIAL_STOP_KEYS = {
    html_label_key(label)
    for label in [
        *TOP_LEVEL_FEATURES,
        *L2_FEATURES,
        "Buttons",
        "Mechanical",
        "Connectivity",
        "Network",
        "Notes",
        "Notes:",
    ]
}

def run_command(command: list[str], cwd: Path) -> None:
    print("RUN\t" + " ".join(command))
    completed = subprocess.run(command, cwd=str(cwd))
    if completed.returncode:
        raise SystemExit(completed.returncode)


def strip_sdw_markers(value: str) -> str:
    lines = [
        line
        for line in value.splitlines()
        if not line.startswith("__HTML_DISPLAY_TABLE_ROW__") and line.strip() != "__HTML_SOURCE_SPEC__"
    ]
    return "\n".join(lines).strip() + "\n"


def prepare_text_dirs(converted: list[dict[str, str]], sdw_text_dir: Path, full_text_dir: Path) -> list[dict[str, str]]:
    full_text_dir.mkdir(parents=True, exist_ok=True)
    prepared: list[dict[str, str]] = []
    for item in converted:
        sdw_text = Path(item["text_spec"])
        full_text = full_text_dir / sdw_text.name
        full_text.write_text(strip_sdw_markers(sdw_text.read_text(encoding="utf-8")), encoding="utf-8")
        prepared.append({**item, "full_text_spec": str(full_text), "sdw_text_spec": str(sdw_text)})
    return prepared


def run_full_generator(
    scripts_dir: Path,
    config_key: str,
    text_dir: Path,
    output_xlsx: Path,
    workbook_layout: str,
    work_root: Path,
) -> None:
    config = FULL_CONFIGS[config_key]
    command = [
        sys.executable,
        str(config["script"]),
        "--spec-dir",
        str(text_dir),
        "--glob",
        "*_Spec.txt",
        "--output-xlsx",
        str(output_xlsx),
        "--workbook-layout",
        workbook_layout,
        "--runtime-text-dir",
        str(work_root / "analysis_output" / str(config["runtime_dir"])),
        "--generated-text-dir",
        str(work_root / "analysis_output" / str(config["generated_dir"])),
    ]
    command.extend(str(value) for value in config.get("extra_args", []))
    print("Starting full ShortSpec generator...")
    run_command(command, scripts_dir)
    print("Completed full ShortSpec generator.")


def run_sdw_generators(
    scripts_dir: Path,
    config_key: str,
    text_dir: Path,
    temp_root: Path,
    workbook_layout: str,
    work_root: Path,
) -> list[tuple[str, Path]]:
    config = SDW_CONFIGS[config_key]
    feature_outputs: list[tuple[str, Path]] = []
    for feature_name, script_name, runtime_dir_name, generated_dir_name, temp_file_name in config["features"]:  # type: ignore[index]
        temp_output = temp_root / str(temp_file_name)
        command = [
            sys.executable,
            str(script_name),
            "--spec-dir",
            str(text_dir),
            "--glob",
            "*_Spec.txt",
            "--output-xlsx",
            str(temp_output),
            "--workbook-layout",
            workbook_layout,
            "--runtime-text-dir",
            str(work_root / "analysis_output" / str(runtime_dir_name)),
            "--generated-text-dir",
            str(work_root / "analysis_output" / str(generated_dir_name)),
        ]
        print(f"Starting {feature_name} HTML SDW generator...")
        run_command(command, scripts_dir)
        print(f"Completed {feature_name} HTML SDW generator.")
        feature_outputs.append((str(feature_name), temp_output))
    return feature_outputs


def row_value(row: list[str], index: int) -> str:
    return row[index] if index < len(row) else ""


def product_key(value: str) -> str:
    return " ".join(value.lower().split())


def read_summary_rows(path: Path) -> list[list[str]]:
    sheets = read_workbook_sheets(path)
    if not sheets:
        raise RuntimeError(f"No worksheets found in workbook: {path}")
    rows = sheets[0][1]
    if not rows or [cell.strip().lower() for cell in rows[0][:4]] != ["product", "l1 feature", "l2 feature", "short spec"]:
        raise RuntimeError(f"Expected single-sheet summary workbook with Product/L1/L2/Short Spec columns: {path}")
    return rows


def collect_sdw_rows(feature_outputs: list[tuple[str, Path]]) -> dict[str, dict[str, list[str]]]:
    rows_by_product: dict[str, dict[str, list[str]]] = {}
    for _, workbook_path in feature_outputs:
        for _, rows in read_workbook_sheets(workbook_path):
            if not rows:
                continue
            rows = normalize_short_spec_rows(rows)
            for row in rows[1:]:
                product = row_value(row, 0)
                l2_feature = row_value(row, 2)
                if not product or l2_feature not in SDW_L2_FEATURES:
                    continue
                rows_by_product.setdefault(product_key(product), {})[l2_feature] = [
                    product,
                    row_value(row, 1),
                    l2_feature,
                    row_value(row, 3),
                ]
    return rows_by_product


def clean_case_material_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return value


def render_case_material_cell(values: list[str]) -> str:
    values = [value for value in values if value]
    if len(values) == 1:
        return values[0]
    return "\n".join(f"- {value}" for value in values)


def extract_html_case_material_values(spec_text: str) -> list[str]:
    values: list[str] = []
    active = False
    for raw_line in spec_text.splitlines():
        line = clean_case_material_value(raw_line)
        if not line:
            continue
        key = html_label_key(line)
        if key == html_label_key(HTML_CASE_MATERIAL_FEATURE):
            active = True
            continue
        if not active:
            continue
        if line == HTML_SOURCE_MARKER or key in HTML_CASE_MATERIAL_STOP_KEYS:
            break
        values.append(line)
    return values


def collect_html_case_material_rows(converted: list[dict[str, str]]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for item in converted:
        text_spec = Path(item["sdw_text_spec"])
        values = extract_html_case_material_values(text_spec.read_text(encoding="utf-8"))
        if not values:
            continue
        product = derive_display_name(text_spec)
        rows[product_key(product)] = [product, "DESIGN", HTML_CASE_MATERIAL_FEATURE, render_case_material_cell(values)]
    return rows


class HtmlFeatureValueParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.feature_depth = 0
        self.feature_spec = ""
        self.h3_depth = 0
        self.h3_parts: list[str] = []
        self.current_feature = ""
        self.value_depth = 0
        self.value_parts: list[str] = []
        self.current_values: list[str] = []
        self.features: list[tuple[str, str, list[str]]] = []

    def in_feature(self) -> bool:
        return self.feature_depth > 0

    def start_feature(self, specstructure: str) -> None:
        self.feature_spec = specstructure
        self.current_feature = ""
        self.h3_parts = []
        self.value_parts = []
        self.current_values = []
        self.feature_depth = 1

    def flush_value(self) -> None:
        value = clean_html_keyboard_value(" ".join(self.value_parts))
        if value:
            self.current_values.append(value)
        self.value_parts = []

    def finish_feature(self) -> None:
        self.flush_value()
        feature_name = clean_html_keyboard_value(self.current_feature)
        if feature_name and self.current_values:
            self.features.append((self.feature_spec, feature_name, self.current_values.copy()))
        self.feature_spec = ""
        self.current_feature = ""
        self.h3_parts = []
        self.value_parts = []
        self.current_values = []
        self.feature_depth = 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        classes = class_tokens(attrs)

        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in SKIP_TAGS or has_display_none(attrs) or "as_note_type" in classes:
            self.skip_depth = 1
            return

        specstructure = attrs.get("specstructure", "")
        if tag == "div" and specstructure:
            if self.in_feature():
                self.finish_feature()
            self.start_feature(specstructure)
            return

        if self.in_feature():
            self.feature_depth += 1

        if tag == "h3" and self.in_feature():
            self.h3_depth = 1
            self.h3_parts = []
            return
        if self.h3_depth:
            self.h3_depth += 1

        if tag == "div" and self.in_feature() and "divFeatureValue" in classes:
            self.value_depth = 1
            self.value_parts = []
            return
        if self.value_depth:
            if tag in BLOCK_TAGS:
                self.flush_value()
            self.value_depth += 1

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        if self.skip_depth or tag in SKIP_TAGS or has_display_none(attrs):
            return
        if self.value_depth and tag in BLOCK_TAGS:
            self.flush_value()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return

        if self.h3_depth:
            self.h3_depth -= 1
            if self.h3_depth == 0:
                self.current_feature = clean_html_keyboard_value(" ".join(self.h3_parts))
                self.h3_parts = []

        if self.value_depth:
            if tag in BLOCK_TAGS:
                self.flush_value()
            self.value_depth -= 1
            if self.value_depth == 0:
                self.flush_value()

        if self.in_feature():
            self.feature_depth -= 1
            if self.feature_depth == 0:
                self.finish_feature()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned:
            return
        if self.h3_depth:
            self.h3_parts.append(cleaned)
        if self.value_depth:
            self.value_parts.append(cleaned)


def clean_html_keyboard_value(value: str) -> str:
    value = value.replace("\ufeff", "")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\([^()]*\)", "", value)
        value = re.sub(r"（[^（）]*）", "", value)
    value = re.sub(r"[\u2022\u25aa\u25ab\u25b8\u25ba\u25cf\u25c6\u25c7\u25a0]+", "", value)
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",\s*,", ",", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n,;")


def unique_clean_values(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = clean_html_keyboard_value(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def extract_html_feature_values(html_text: str, feature_names: set[str]) -> dict[str, list[str]]:
    wanted = {html_label_key(name): name for name in feature_names}
    values: dict[str, list[str]] = {name: [] for name in feature_names}
    parser = HtmlFeatureValueParser()
    parser.feed(html_text)
    parser.close()
    for _spec, feature_name, feature_values in parser.features:
        target_name = wanted.get(html_label_key(feature_name))
        if not target_name:
            continue
        values[target_name].extend(feature_values)
    return values


def strip_keyboard_models_prefix(value: str) -> str:
    value = clean_html_keyboard_value(value)
    return clean_html_keyboard_value(re.sub(r"^.*?models?\s*:\s*", "", value, count=1, flags=re.I))


def strip_keyboard_backlight_prefix(value: str) -> str:
    value = clean_html_keyboard_value(value)
    if ":" not in value:
        return value
    _prefix, suffix = value.split(":", 1)
    return clean_html_keyboard_value(suffix)


def is_ignored_keyboard_option(value: str) -> bool:
    cleaned = clean_html_keyboard_value(value).casefold()
    return "none" in cleaned or cleaned.startswith("no")


def append_optional_star(value: str, starred: bool) -> str:
    value = clean_html_keyboard_value(value)
    if starred and value and not value.endswith("*"):
        return f"{value}*"
    return value


def keyboard_tokens_from_html_value(value: str) -> list[tuple[int, str]]:
    lowered = value.casefold()
    tokens: list[tuple[int, str]] = []
    row_match = re.search(r"\b\d+-row\b", value, flags=re.I)
    if row_match:
        tokens.append((row_match.start(), row_match.group(0)))
    for needle, rendered in [
        ("multimedia fn keys", "multimedia Fn keys"),
        ("spill-resistant", "spill-resistant"),
        ("numeric keypad", "numeric keypad"),
        ("chrome keyboard", "Chrome keyboard"),
    ]:
        index = lowered.find(needle)
        if index >= 0:
            tokens.append((index, rendered))
    return sorted(tokens, key=lambda item: item[0])


def render_mobile_keyboard_option(value: str) -> str:
    tokens = [token for _index, token in keyboard_tokens_from_html_value(value)]
    if tokens:
        return ", ".join(tokens)
    return clean_html_keyboard_value(value)


def split_keyboard_segments(value: str) -> list[str]:
    return [clean_html_keyboard_value(segment) for segment in re.split(r"\s*,\s*", value) if clean_html_keyboard_value(segment)]


def summarize_keyboard_differences_by_option(values: list[str]) -> list[str]:
    segment_lists = [split_keyboard_segments(value) for value in values]
    if len(segment_lists) < 2 or any(not segments for segments in segment_lists):
        return []
    common = set(segment.casefold() for segment in segment_lists[0])
    for segments in segment_lists[1:]:
        common &= {segment.casefold() for segment in segments}
    if not common:
        return []
    return [
        ", ".join(segment for segment in segments if segment.casefold() not in common)
        for segments in segment_lists
    ]


def summarize_mobile_keyboard_values(values: list[str]) -> list[str]:
    normalized = [strip_keyboard_models_prefix(value) for value in values]
    ignored_present = any(is_ignored_keyboard_option(value) for value in normalized)
    positive_values = unique_clean_values([value for value in normalized if not is_ignored_keyboard_option(value)])
    if not positive_values:
        return []

    rendered_by_option = [render_mobile_keyboard_option(value) for value in positive_values]
    extracted_by_option = [
        rendered
        for value, rendered in zip(positive_values, rendered_by_option)
        if keyboard_tokens_from_html_value(value)
    ]
    if (
        len(positive_values) > 1
        and len(extracted_by_option) == len(positive_values)
        and len({value.casefold() for value in extracted_by_option}) == 1
    ):
        output: list[str] = []
        seen: set[str] = set()
        differences = summarize_keyboard_differences_by_option(positive_values)
        for extracted, difference in zip(rendered_by_option, differences):
            combined = extracted
            if difference:
                combined = f"{extracted}, {difference}"
            key = combined.casefold()
            if key in seen:
                continue
            seen.add(key)
            output.append(append_optional_star(combined, ignored_present))
        if output:
            return output

    return [append_optional_star(value, ignored_present) for value in unique_clean_values(rendered_by_option)]


def summarize_direct_keyboard_values(values: list[str]) -> list[str]:
    normalized = [strip_keyboard_models_prefix(value) for value in values]
    ignored_present = any(is_ignored_keyboard_option(value) for value in normalized)
    positive_values = unique_clean_values([value for value in normalized if not is_ignored_keyboard_option(value)])
    return [append_optional_star(value, ignored_present) for value in positive_values]


def remove_backlight_word(value: str) -> str:
    value = re.sub(r"\s*-?\s*\bbacklight\b", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value)
    return clean_html_keyboard_value(value).strip(" -")


def summarize_keyboard_backlight_values(values: list[str]) -> str:
    normalized = [strip_keyboard_backlight_prefix(value) for value in values]
    ignored_present = any(is_ignored_keyboard_option(value) for value in normalized)
    positive_values = unique_clean_values([value for value in normalized if not is_ignored_keyboard_option(value)])
    if not positive_values:
        return ""
    if len(positive_values) == 1:
        return append_optional_star(positive_values[0], ignored_present)
    rendered_values: list[str] = []
    last_index = len(positive_values) - 1
    for index, value in enumerate(positive_values):
        rendered = value if index == last_index else remove_backlight_word(value)
        if not rendered:
            continue
        rendered_values.append(append_optional_star(rendered, ignored_present))
    return " / ".join(rendered_values)


def render_html_keyboard_cell(config_key: str, keyboard_values: list[str], backlight_values: list[str]) -> str:
    if config_key in MOBILE_KEYBOARD_CONFIGS:
        keyboard_lines = summarize_mobile_keyboard_values(keyboard_values)
    else:
        keyboard_lines = summarize_direct_keyboard_values(keyboard_values)
    backlight = summarize_keyboard_backlight_values(backlight_values)
    parts = [*keyboard_lines]
    if backlight:
        parts.append(backlight)
    return "\n".join(part for part in parts if part)


def collect_html_keyboard_rows(converted: list[dict[str, str]], config_key: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for item in converted:
        html_path = Path(item["source_html"])
        values = extract_html_feature_values(
            html_path.read_text(encoding="utf-8-sig", errors="replace"),
            {HTML_KEYBOARD_FEATURE, HTML_KEYBOARD_BACKLIGHT_FEATURE},
        )
        cell = render_html_keyboard_cell(
            config_key,
            values.get(HTML_KEYBOARD_FEATURE, []),
            values.get(HTML_KEYBOARD_BACKLIGHT_FEATURE, []),
        )
        if not cell:
            continue
        text_spec = Path(item["sdw_text_spec"])
        product = derive_display_name(text_spec)
        rows[product_key(product)] = [product, "DESIGN", HTML_KEYBOARD_FEATURE, cell]
    return rows


def clean_other_certification_value(value: str) -> str:
    value = value.replace("\ufeff", "")
    value = value.replace("\u00a0", " ")
    value = value.replace("®", "")
    value = value.replace("™", "")
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = re.sub(r"[\u2022\u25aa\u25ab\u25b8\u25ba\u25cf\u25c6\u25c7\u25a0]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n,;")


def is_mil_spec_work_in_progress(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return normalized == "work in progress"


def normalize_other_certification_option(value: str) -> str:
    value = clean_other_certification_value(value)
    if not value:
        return ""

    starred = False
    if re.search(r"\(Optional\)", value, flags=re.I):
        value = re.sub(r"\s*\(Optional\)\s*", " ", value, flags=re.I)
        starred = True

    model_prefix = r"^(?:.+?\s+)?models?\s*:\s*"
    if re.match(model_prefix, value, flags=re.I):
        value = re.sub(model_prefix, "", value, count=1, flags=re.I)
        starred = True

    value = clean_other_certification_value(value)
    if not value:
        return ""
    if starred and not value.endswith("*"):
        value = f"{value}*"
    return value.strip()


def render_other_certifications_cell(values_by_field: dict[str, list[str]]) -> str:
    rendered: list[str] = []
    seen: set[str] = set()
    for field_name in (HTML_OTHER_CERTIFICATIONS_FEATURE, HTML_MIL_SPEC_FEATURE):
        for value in values_by_field.get(field_name, []):
            normalized = normalize_other_certification_option(value)
            if not normalized:
                continue
            dedupe_key = normalized.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rendered.append(normalized)
    return "\n".join(rendered)


class HtmlOtherCertificationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.feature_depth = 0
        self.h3_depth = 0
        self.h3_parts: list[str] = []
        self.current_feature = ""
        self.value_depth = 0
        self.value_parts: list[str] = []
        self.current_values: list[str] = []
        self.features: list[tuple[str, list[str]]] = []

    def in_other_certification_feature(self) -> bool:
        return self.feature_depth > 0

    def start_feature(self) -> None:
        self.current_feature = ""
        self.h3_parts = []
        self.value_parts = []
        self.current_values = []

    def flush_value(self) -> None:
        value = clean_other_certification_value(" ".join(self.value_parts))
        if value:
            self.current_values.append(value)
        self.value_parts = []

    def finish_feature(self) -> None:
        self.flush_value()
        feature_name = clean_other_certification_value(self.current_feature)
        if feature_name and self.current_values:
            self.features.append((feature_name, self.current_values.copy()))
        self.current_feature = ""
        self.h3_parts = []
        self.value_parts = []
        self.current_values = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        classes = class_tokens(attrs)

        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in SKIP_TAGS or has_display_none(attrs) or "as_note_type" in classes:
            self.skip_depth = 1
            return

        if tag == "div" and html_label_key(attrs.get("specstructure", "")) == HTML_OTHER_CERTIFICATIONS_SPEC_KEY:
            self.start_feature()
            self.feature_depth = 1
            return

        if self.in_other_certification_feature():
            self.feature_depth += 1

        if tag == "h3" and self.in_other_certification_feature():
            self.h3_depth = 1
            self.h3_parts = []
            return
        if self.h3_depth:
            self.h3_depth += 1

        if tag == "div" and self.in_other_certification_feature() and "divFeatureValue" in classes:
            self.value_depth = 1
            self.value_parts = []
            return
        if self.value_depth:
            if tag in BLOCK_TAGS:
                self.flush_value()
            self.value_depth += 1

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        if self.skip_depth or tag in SKIP_TAGS or has_display_none(attrs):
            return
        if self.value_depth and tag in BLOCK_TAGS:
            self.flush_value()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return

        if self.h3_depth:
            self.h3_depth -= 1
            if self.h3_depth == 0:
                self.current_feature = clean_other_certification_value(" ".join(self.h3_parts))
                self.h3_parts = []

        if self.value_depth:
            if tag in BLOCK_TAGS:
                self.flush_value()
            self.value_depth -= 1
            if self.value_depth == 0:
                self.flush_value()

        if self.in_other_certification_feature():
            self.feature_depth -= 1
            if self.feature_depth == 0:
                self.finish_feature()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned:
            return
        if self.h3_depth:
            self.h3_parts.append(cleaned)
        if self.value_depth:
            self.value_parts.append(cleaned)


def extract_html_other_certification_values(html_text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {
        HTML_OTHER_CERTIFICATIONS_FEATURE: [],
        HTML_MIL_SPEC_FEATURE: [],
    }
    parser = HtmlOtherCertificationParser()
    parser.feed(html_text)
    parser.close()

    for feature_name, feature_values in parser.features:
        target_field = (
            HTML_MIL_SPEC_FEATURE
            if html_label_key(feature_name) == html_label_key(HTML_MIL_SPEC_FEATURE)
            else HTML_OTHER_CERTIFICATIONS_FEATURE
        )
        for raw_value in feature_values:
            line = clean_other_certification_value(raw_value)
            if not line:
                continue
            if target_field == HTML_MIL_SPEC_FEATURE and is_mil_spec_work_in_progress(line):
                continue
            if html_label_key(line) == HTML_OTHER_CERTIFICATIONS_SPEC_KEY:
                continue
            if html_label_key(line) == html_label_key(HTML_MIL_SPEC_FEATURE):
                continue
            values[target_field].append(line)
    return values


def collect_html_other_certification_rows(converted: list[dict[str, str]]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for item in converted:
        html_path = Path(item["source_html"])
        values = extract_html_other_certification_values(
            html_path.read_text(encoding="utf-8-sig", errors="replace")
        )
        cell = render_other_certifications_cell(values)
        if not cell:
            continue
        text_spec = Path(item["sdw_text_spec"])
        product = derive_display_name(text_spec)
        rows[product_key(product)] = [product, "CERTIFICATIONS", HTML_OTHER_CERTIFICATIONS_FEATURE, cell]
    return rows


def overlay_sdw_rows(full_rows: list[list[str]], sdw_rows: dict[str, dict[str, list[str]]]) -> list[list[str]]:
    if not full_rows:
        return full_rows

    output: list[list[str]] = [full_rows[0]]
    inserted: dict[str, set[str]] = {}

    for row in full_rows[1:]:
        product = row_value(row, 0)
        l2_feature = row_value(row, 2)
        key = product_key(product)
        replacements = sdw_rows.get(key, {})
        if l2_feature in SDW_L2_FEATURES:
            replacement = replacements.get(l2_feature)
            if replacement:
                output.append(replacement)
                inserted.setdefault(key, set()).add(l2_feature)
            continue
        output.append(row)

    products_in_order = []
    seen_products = set()
    for row in full_rows[1:]:
        key = product_key(row_value(row, 0))
        if key and key not in seen_products:
            seen_products.add(key)
            products_in_order.append(key)

    for key in products_in_order:
        for l2_feature in ("Storage", "Display", "WLAN + Bluetooth"):
            if l2_feature in inserted.get(key, set()):
                continue
            replacement = sdw_rows.get(key, {}).get(l2_feature)
            if replacement:
                output.append(replacement)

    return output


def overlay_html_other_certification_rows(
    full_rows: list[list[str]], other_rows: dict[str, list[str]]
) -> list[list[str]]:
    if not full_rows:
        return full_rows

    output: list[list[str]] = [full_rows[0]]
    inserted: set[str] = set()
    products_with_original_other = {
        product_key(row_value(row, 0))
        for row in full_rows[1:]
        if row_value(row, 2) == HTML_OTHER_CERTIFICATIONS_FEATURE
    }

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
        replacement = other_rows.get(key)

        if l2_feature == HTML_OTHER_CERTIFICATIONS_FEATURE:
            if replacement:
                output.append(replacement)
                inserted.add(key)
            continue

        output.append(row)
        if (
            l2_feature == "Green Certifications"
            and key not in products_with_original_other
            and replacement
            and key not in inserted
        ):
            output.append(replacement)
            inserted.add(key)

    for key in products_in_order:
        replacement = other_rows.get(key)
        if replacement and key not in inserted:
            output.append(replacement)

    return output


def overlay_html_keyboard_rows(full_rows: list[list[str]], keyboard_rows: dict[str, list[str]]) -> list[list[str]]:
    if not full_rows:
        return full_rows

    output: list[list[str]] = [full_rows[0]]
    inserted: set[str] = set()
    products_with_original_keyboard = {
        product_key(row_value(row, 0))
        for row in full_rows[1:]
        if row_value(row, 2) == HTML_KEYBOARD_FEATURE
    }

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
        replacement = keyboard_rows.get(key)

        if l2_feature == HTML_KEYBOARD_FEATURE:
            if replacement:
                output.append(replacement)
                inserted.add(key)
            continue

        output.append(row)
        if (
            l2_feature == "Pen"
            and replacement
            and key not in inserted
            and key not in products_with_original_keyboard
        ):
            output.append(replacement)
            inserted.add(key)

    for key in products_in_order:
        replacement = keyboard_rows.get(key)
        if replacement and key not in inserted:
            output.append(replacement)

    return output


def remove_l2_feature_rows(full_rows: list[list[str]], l2_feature: str) -> list[list[str]]:
    if not full_rows:
        return full_rows
    return [full_rows[0], *[row for row in full_rows[1:] if row_value(row, 2) != l2_feature]]


def overlay_html_case_material_rows(full_rows: list[list[str]], case_rows: dict[str, list[str]]) -> list[list[str]]:
    if not full_rows:
        return full_rows

    output: list[list[str]] = [full_rows[0]]
    inserted: set[str] = set()
    products_with_original_case = {
        product_key(row_value(row, 0))
        for row in full_rows[1:]
        if row_value(row, 2) == HTML_CASE_MATERIAL_FEATURE
    }

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
        replacement = case_rows.get(key)

        if l2_feature == HTML_CASE_MATERIAL_FEATURE:
            if replacement:
                output.append(replacement)
                inserted.add(key)
            continue

        output.append(row)
        if (
            l2_feature == "Color"
            and key not in products_with_original_case
            and replacement
            and key not in inserted
        ):
            output.append(replacement)
            inserted.add(key)

    for key in products_in_order:
        replacement = case_rows.get(key)
        if replacement and key not in inserted:
            output.append(replacement)

    return output


def write_final_manifest(
    manifest_path: Path,
    output_xlsx: Path,
    converted: list[dict[str, str]],
    full_workbook: Path,
    sdw_outputs: list[tuple[str, Path]],
    overridden_features: set[str],
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "workbook": str(output_xlsx),
        "converted": converted,
        "full_rule_source": "PDF full ShortSpec rule-based deliverable short_spec_generator_260525",
        "sdw_rule_source": (
            "HTML SDW deliverable sdw_html_260625. WLAN first coalesces HTML WLAN options whose first two "
            "comma-separated segments are identical, treating each such group as one WLAN option before existing WLAN selection logic."
        ),
        "case_material_rule_source": "HTML Case Material direct field override; omitted when HTML Case Material is absent",
        "keyboard_rule_source": (
            "HTML Keyboard and Keyboard Backlight feature override; mobile product lines extract row count, "
            "multimedia Fn keys, spill-resistant, numeric keypad, and Chrome keyboard from Keyboard values unless none are present; "
            "when multiple positive Keyboard options produce the same extracted value, each option emits that extracted value followed by its differing non-common parts; "
            "desktop and ThinkStation use direct Keyboard values; Keyboard Backlight uses direct positive values joined by ' / ', with only the last value retaining 'backlight'; "
            "None/No options are omitted and mark all remaining output options with '*'; model prefixes and parenthesized text are removed"
        ),
        "other_certifications_rule_source": (
            "HTML div[specstructure='Other Certifications'] feature values for non-ThinkStation; "
            "Other Certifications feature values are emitted before Mil-Spec Test values; registered/trademark symbols are removed; "
            "Mil-Spec Test value 'Work in progress' is ignored; omitted when the HTML div tag is absent; omitted for ThinkStation"
        ),
        "full_workbook": str(full_workbook),
        "sdw_workbooks": [{"feature": feature, "workbook": str(path)} for feature, path in sdw_outputs],
        "overridden_features": sorted(overridden_features),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HTML-source full ShortSpec generation with HTML SDW overrides.")
    parser.add_argument("--config", required=True, choices=sorted(FULL_CONFIGS), help="Product-line configuration key.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-dir", help="Directory containing source HTML files.")
    source_group.add_argument("--html-files", nargs="+", help="One or more source HTML files.")
    parser.add_argument("--glob", default="*.html", help="Glob used with --source-dir. Default: *.html")
    parser.add_argument("--output-xlsx", required=True, help="Final combined Excel workbook path.")
    parser.add_argument(
        "--work-dir",
        help="Directory for manifests, temporary converted specs, and intermediate workbooks. Default: _work next to the output workbook.",
    )
    parser.add_argument(
        "--workbook-layout",
        choices=["single_sheet_summary"],
        default="single_sheet_summary",
        help="The full HTML deliverable writes one summary worksheet.",
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
    temp_root = work_root / "analysis_output" / f"html_all_tmp_{os.getpid()}_{int(time.time())}"
    sdw_text_dir = temp_root / "sdw_text"
    full_text_dir = temp_root / "full_text"
    full_workbook = temp_root / "full.xlsx"
    final_manifest = work_root / "manifests" / f"{output_xlsx.stem}.json"

    html_paths = collect_html_paths(args.source_dir, args.glob, args.html_files)
    print(FULL_CONFIGS[args.config]["title"])
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
        sdw_outputs = run_sdw_generators(scripts_dir, args.config, sdw_text_dir, temp_root, args.workbook_layout, work_root)

        full_rows = read_summary_rows(full_workbook)
        merged_rows = overlay_sdw_rows(full_rows, collect_sdw_rows(sdw_outputs))
        overridden_features = set(SDW_L2_FEATURES)
        html_overrides = product_rule_module(args.config, "html_overrides")
        merged_rows = overlay_html_keyboard_rows(
            merged_rows,
            html_overrides.collect_html_keyboard_rows(converted, args.config),
        )
        overridden_features.add(HTML_KEYBOARD_FEATURE)
        if args.config != "ts":
            merged_rows = overlay_html_case_material_rows(merged_rows, collect_html_case_material_rows(converted))
            merged_rows = overlay_html_other_certification_rows(
                merged_rows,
                html_overrides.collect_html_other_certification_rows(converted),
            )
            overridden_features.add(HTML_CASE_MATERIAL_FEATURE)
            overridden_features.add(HTML_OTHER_CERTIFICATIONS_FEATURE)
        else:
            merged_rows = remove_l2_feature_rows(merged_rows, HTML_OTHER_CERTIFICATIONS_FEATURE)
            overridden_features.add(HTML_OTHER_CERTIFICATIONS_FEATURE)
        write_xlsx(output_xlsx, [("All Products", merged_rows)], workbook_layout="per_product")
        write_final_manifest(final_manifest, output_xlsx, converted, full_workbook, sdw_outputs, overridden_features)
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
