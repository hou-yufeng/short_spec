from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path


CONFIGS: dict[str, dict[str, object]] = {
    "com": {
        "title": "Lenovo Commercial Laptop Storage Display Wi-Fi ShortSpec HTML Source",
        "features": [
            ("Storage", "batch_generate_storage_shortspec_excel_rule_based.py", "runtime_html_storage_com", "generated_html_storage_com", "st.xlsx"),
            ("Display", "batch_generate_display_shortspec_excel_rule_based.py", "runtime_html_display_com", "generated_html_display_com", "dp.xlsx"),
            ("WLAN", "batch_generate_wlan_shortspec_excel_rule_based.py", "runtime_html_wlan_com", "generated_html_wlan_com", "wf.xlsx"),
        ],
    },
    "con": {
        "title": "Lenovo Consumer Laptop Storage Display Wi-Fi ShortSpec HTML Source",
        "features": [
            ("Storage", "batch_generate_storage_shortspec_excel_rule_based_consumer.py", "runtime_html_storage_con", "generated_html_storage_con", "st.xlsx"),
            ("Display", "batch_generate_display_shortspec_excel_rule_based_consumer.py", "runtime_html_display_con", "generated_html_display_con", "dp.xlsx"),
            ("WLAN", "batch_generate_wlan_shortspec_excel_rule_based_consumer.py", "runtime_html_wlan_con", "generated_html_wlan_con", "wf.xlsx"),
        ],
    },
    "smb": {
        "title": "Lenovo SMB Laptop Storage Display Wi-Fi ShortSpec HTML Source",
        "features": [
            ("Storage", "batch_generate_storage_shortspec_excel_rule_based_smb.py", "runtime_html_storage_smb", "generated_html_storage_smb", "st.xlsx"),
            ("Display", "batch_generate_display_shortspec_excel_rule_based_smb.py", "runtime_html_display_smb", "generated_html_display_smb", "dp.xlsx"),
            ("WLAN", "batch_generate_wlan_shortspec_excel_rule_based_smb.py", "runtime_html_wlan_smb", "generated_html_wlan_smb", "wf.xlsx"),
        ],
    },
    "tab": {
        "title": "Lenovo Tablet Storage Display Wi-Fi ShortSpec HTML Source",
        "features": [
            ("Storage", "batch_generate_storage_shortspec_excel_rule_based_tablet.py", "runtime_html_storage_tab", "generated_html_storage_tab", "st.xlsx"),
            ("Display", "batch_generate_display_shortspec_excel_rule_based_tablet.py", "runtime_html_display_tab", "generated_html_display_tab", "dp.xlsx"),
            ("WLAN", "batch_generate_wlan_shortspec_excel_rule_based_tablet.py", "runtime_html_wlan_tab", "generated_html_wlan_tab", "wf.xlsx"),
        ],
    },
    "dt": {
        "title": "Lenovo Desktop Storage Display Wi-Fi ShortSpec HTML Source",
        "features": [
            ("Storage", "batch_generate_storage_shortspec_excel_rule_based_dt.py", "runtime_html_storage_dt", "generated_html_storage_dt", "st.xlsx"),
            ("Display", "batch_generate_display_shortspec_excel_rule_based_dt.py", "runtime_html_display_dt", "generated_html_display_dt", "dp.xlsx"),
            ("WLAN", "batch_generate_wlan_shortspec_excel_rule_based_dt.py", "runtime_html_wlan_dt", "generated_html_wlan_dt", "wf.xlsx"),
        ],
    },
    "ts": {
        "title": "Lenovo ThinkStation Storage Wi-Fi ShortSpec HTML Source",
        "features": [
            ("Storage", "batch_generate_storage_shortspec_excel_rule_based_thinkstation.py", "runtime_html_storage_ts", "generated_html_storage_ts", "st.xlsx"),
            ("WLAN", "batch_generate_wlan_shortspec_excel_rule_based_thinkstation.py", "runtime_html_wlan_ts", "generated_html_wlan_ts", "wf.xlsx"),
        ],
    },
}


BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "caption",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "ol",
    "p",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


SKIP_TAGS = {"script", "style", "noscript", "svg", "sup"}


def attr_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name.lower(): value or "" for name, value in attrs}


def class_tokens(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


def has_display_none(attrs: dict[str, str]) -> bool:
    return "display:none" in attrs.get("style", "").replace(" ", "").lower()


class SpecContentTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.current: list[str] = []
        self.capturing = False
        self.skip_depth = 0
        self.product_title_parts: list[str] = []
        self.title_depth: int | None = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        classes = class_tokens(attrs)

        if tag == "div" and "titleProductName" in classes:
            self.title_depth = 1
        elif self.title_depth is not None:
            self.title_depth += 1

        if tag == "div" and "spec-content" in classes:
            self.capturing = True
            self.flush()
            return

        if not self.capturing:
            return

        if self.skip_depth:
            self.skip_depth += 1
            return

        if tag in SKIP_TAGS or has_display_none(attrs) or "as_note_type" in classes:
            self.skip_depth = 1
            return

        if tag in BLOCK_TAGS:
            self.flush()

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.capturing and tag in BLOCK_TAGS:
            self.flush()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.title_depth is not None:
            self.title_depth -= 1
            if self.title_depth <= 0:
                self.title_depth = None

        if not self.capturing:
            return

        if self.skip_depth:
            self.skip_depth -= 1
            return

        if tag in BLOCK_TAGS:
            self.flush()

        if tag == "body":
            self.capturing = False

    def handle_data(self, data: str) -> None:
        if self.title_depth is not None:
            cleaned = re.sub(r"\s+", " ", data).strip()
            if cleaned:
                self.product_title_parts.append(cleaned)

        if not self.capturing or self.skip_depth:
            return

        parts = re.split(r"(\n+)", data)
        for part in parts:
            if not part:
                continue
            if "\n" in part:
                self.flush()
                continue
            cleaned = re.sub(r"\s+", " ", part).strip()
            if cleaned:
                self.current.append(cleaned)

    def flush(self) -> None:
        if not self.current:
            return
        text = html.unescape(" ".join(self.current))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            self.lines.append(text)
        self.current = []

    @property
    def product_title(self) -> str:
        title = " ".join(self.product_title_parts)
        title = re.sub(r"\s*Last Modify Time:.*$", "", title).strip()
        return title or "Document"


def normalize_product_filename(title: str) -> str:
    value = html.unescape(title)
    value = re.sub(r"\([^)]*\)", lambda match: " " + match.group(0).strip("()") + " ", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "Document"


HTML_STORAGE_FIELD_LABELS = {
    "max storage support",
    "storage support",
    "storage slot",
    "storage slots",
    "storage type",
    "storage controllers",
    "storage controller",
    "raid",
}

HTML_STORAGE_KEEP_LABELS = {"max storage support", "storage support", "raid"}

HTML_STORAGE_SECTION_END_LABELS = {
    "audio",
    "battery",
    "camera",
    "certifications",
    "connectivity",
    "display",
    "environmental",
    "input device",
    "keyboard",
    "mechanical",
    "memory",
    "monitor support",
    "multi media",
    "network",
    "operating requirements",
    "pen",
    "ports",
    "power adapter",
    "power supply",
    "processor",
    "removable storage",
    "security & privacy",
    "service",
    "software",
    "sustainability",
    "touchpad",
    "touchscreen",
    "weight",
}


def html_label_key(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = re.sub(r"\*+$", "", value)
    value = re.sub(r"[^a-z0-9+&/(). -]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip(" :")


HTML_DISPLAY_TABLE_ROW_PREFIX = "__HTML_DISPLAY_TABLE_ROW__"
HTML_SOURCE_MARKER = "__HTML_SOURCE_SPEC__"


def clean_html_table_cell(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("\ufeff", "")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


class HtmlDisplayTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.spec_stack: list[str] = []
        self.h3_depth = 0
        self.h3_parts: list[str] = []
        self.current_h3 = ""
        self.skip_depth = 0
        self.table_depth = 0
        self.table_rows: list[list[str]] = []
        self.current_row: list[str] | None = None
        self.cell_depth = 0
        self.cell_parts: list[str] = []
        self.display_rows: list[dict[str, str]] = []

    def in_display_spec(self) -> bool:
        return any(html_label_key(item) == "display" for item in self.spec_stack if item)

    def should_capture_display_table(self) -> bool:
        return self.in_display_spec() and html_label_key(self.current_h3) == "display"

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        if tag == "div":
            self.spec_stack.append(attrs.get("specstructure", ""))

        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in SKIP_TAGS or has_display_none(attrs) or "as_note_type" in class_tokens(attrs):
            self.skip_depth = 1
            return

        if tag == "h3" and self.in_display_spec():
            self.h3_depth = 1
            self.h3_parts = []
            return
        if self.h3_depth:
            self.h3_depth += 1

        if tag == "table":
            if self.table_depth:
                self.table_depth += 1
            elif self.should_capture_display_table():
                self.table_depth = 1
                self.table_rows = []
            return

        if not self.table_depth:
            return
        if tag == "tr":
            self.current_row = []
        elif tag in {"td", "th"}:
            self.cell_depth = 1
            self.cell_parts = []
        elif self.cell_depth:
            self.cell_depth += 1

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        if self.cell_depth and tag.lower() == "br":
            self.cell_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return

        if self.cell_depth:
            if tag in {"td", "th"} and self.cell_depth == 1:
                value = clean_html_table_cell(" ".join(self.cell_parts))
                if self.current_row is not None:
                    self.current_row.append(value)
                self.cell_parts = []
                self.cell_depth = 0
                return
            self.cell_depth -= 1

        if self.table_depth:
            if tag == "tr" and self.current_row is not None:
                if any(cell for cell in self.current_row):
                    self.table_rows.append(self.current_row)
                self.current_row = None
                return
            if tag == "table":
                self.table_depth -= 1
                if self.table_depth == 0:
                    self.finalize_table()
                return

        if self.h3_depth:
            self.h3_depth -= 1
            if self.h3_depth == 0:
                self.current_h3 = clean_html_table_cell(" ".join(self.h3_parts))
                self.h3_parts = []

        if tag == "div" and self.spec_stack:
            self.spec_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned:
            return
        if self.h3_depth:
            self.h3_parts.append(cleaned)
        if self.cell_depth:
            self.cell_parts.append(cleaned)

    def finalize_table(self) -> None:
        if len(self.table_rows) < 2:
            return
        headers = [clean_html_table_cell(value) for value in self.table_rows[0]]
        header_keys = {html_label_key(value) for value in headers}
        if "size" not in header_keys or "resolution" not in header_keys:
            return
        for row in self.table_rows[1:]:
            values = [clean_html_table_cell(value) for value in row]
            item = {
                header: values[index] if index < len(values) else ""
                for index, header in enumerate(headers)
                if header
            }
            if any(item.values()):
                self.display_rows.append(item)


def extract_html_display_table_lines(html_text: str) -> list[str]:
    parser = HtmlDisplayTableParser()
    parser.feed(html_text)
    lines: list[str] = []
    for row in parser.display_rows:
        lines.append(f"{HTML_DISPLAY_TABLE_ROW_PREFIX}\t{json.dumps(row, ensure_ascii=False)}")
    return lines


def keep_html_storage_fields(lines: list[str]) -> list[str]:
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if html_label_key(line) != "storage":
            output.append(line)
            index += 1
            continue

        output.append(line)
        index += 1
        active_label = ""

        while index < len(lines):
            line = lines[index]
            key = html_label_key(line)
            if key in HTML_STORAGE_SECTION_END_LABELS:
                break
            if key in HTML_STORAGE_FIELD_LABELS:
                active_label = key if key in HTML_STORAGE_KEEP_LABELS else ""
                if active_label:
                    output.append(line)
                index += 1
                continue
            if key in {"notes", "notes:"} or line.startswith("["):
                active_label = ""
                index += 1
                continue
            if active_label:
                output.append(line)
            index += 1

    return output


def normalize_html_spec_lines(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    in_max_storage = False
    storage_stop_labels = {
        "Storage Slot",
        "Storage Slots",
        "Storage Type",
        "Storage Controllers",
        "Storage Controller",
        "RAID",
        "Removable Storage",
    }

    for line in lines:
        clean = re.sub(r"\s+", " ", line).strip()
        if not clean:
            continue

        if clean == "Max Storage Support":
            in_max_storage = True
            normalized.append(clean)
            continue

        if in_max_storage and clean in storage_stop_labels:
            in_max_storage = False

        if in_max_storage:
            match = re.match(r"^Up to (?P<count>\d+)x (?P<kind>.+)$", clean, flags=re.I)
            if match:
                count = match.group("count")
                clean = f"Up to {count} drives, {count}x {match.group('kind')}"

        normalized.append(clean)
    return keep_html_storage_fields(normalized)


def html_to_text(html_path: Path) -> tuple[str, str]:
    source = html_path.read_text(encoding="utf-8-sig", errors="replace")
    parser = SpecContentTextParser()
    parser.feed(source)
    parser.flush()
    lines = normalize_html_spec_lines(parser.lines)
    lines.extend(extract_html_display_table_lines(source))
    lines.append(HTML_SOURCE_MARKER)
    text = "\n".join(lines)
    if not text:
        raise RuntimeError(f"No spec-content text found in HTML: {html_path}")
    return parser.product_title, text + "\n"


def collect_html_paths(source_dir: str | None, glob_pattern: str, html_files: list[str] | None) -> list[Path]:
    paths: list[Path] = []
    if html_files:
        paths.extend(Path(item).resolve() for item in html_files)
    if source_dir:
        paths.extend(sorted(Path(source_dir).resolve().glob(glob_pattern)))

    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path)] = path

    result = list(unique.values())
    if not result:
        raise SystemExit("No HTML files found.")
    for path in result:
        if not path.exists():
            raise SystemExit(f"HTML file does not exist: {path}")
    return result


def ensure_inside(path: Path, root: Path) -> None:
    path_resolved = path.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    common = os.path.commonpath([str(path_resolved), str(root_resolved)])
    if os.path.normcase(common) != os.path.normcase(str(root_resolved)):
        raise RuntimeError(f"Refusing to operate outside {root_resolved}: {path_resolved}")


def safe_rmtree(path: Path, root: Path) -> None:
    if path.exists():
        ensure_inside(path, root)
        shutil.rmtree(path)


def convert_html_sources(html_paths: list[Path], text_dir: Path) -> list[dict[str, str]]:
    text_dir.mkdir(parents=True, exist_ok=True)
    converted: list[dict[str, str]] = []
    used_names: set[str] = set()
    for html_path in html_paths:
        product_title, text = html_to_text(html_path)
        base_name = normalize_product_filename(product_title)
        candidate = f"{base_name}_Spec.txt"
        index = 2
        while candidate.lower() in used_names:
            candidate = f"{base_name}_{index}_Spec.txt"
            index += 1
        used_names.add(candidate.lower())

        target = text_dir / candidate
        target.write_text(text, encoding="utf-8")
        converted.append(
            {
                "source_html": str(html_path),
                "product_title": product_title,
                "text_spec": str(target),
            }
        )
    return converted


def run_command(command: list[str], cwd: Path) -> None:
    print("RUN\t" + " ".join(command))
    completed = subprocess.run(command, cwd=str(cwd))
    if completed.returncode:
        raise SystemExit(completed.returncode)


def run_feature(
    scripts_dir: Path,
    feature_name: str,
    script_name: str,
    text_dir: Path,
    temp_output: Path,
    workbook_layout: str,
    runtime_text_dir: Path,
    generated_text_dir: Path,
) -> None:
    command = [
        sys.executable,
        script_name,
        "--spec-dir",
        str(text_dir),
        "--glob",
        "*_Spec.txt",
        "--output-xlsx",
        str(temp_output),
        "--workbook-layout",
        workbook_layout,
        "--runtime-text-dir",
        str(runtime_text_dir),
        "--generated-text-dir",
        str(generated_text_dir),
    ]
    print(f"Starting {feature_name} generator...")
    run_command(command, scripts_dir)
    print(f"Completed {feature_name} generator.")


def merge_features(
    scripts_dir: Path,
    output_xlsx: Path,
    feature_outputs: list[tuple[str, Path]],
    manifest_json: Path,
) -> None:
    command = [
        sys.executable,
        "merge_feature_workbooks.py",
        "--output-xlsx",
        str(output_xlsx),
        "--manifest-json",
        str(manifest_json),
    ]
    for feature_name, path in feature_outputs:
        command.extend(["--feature", feature_name, str(path)])
    print("Merging feature workbooks...")
    run_command(command, scripts_dir)
    print("Completed workbook merge.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HTML-source Storage/Display/WLAN integrated ShortSpec generation.")
    parser.add_argument("--config", required=True, choices=sorted(CONFIGS), help="Product-line configuration key.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-dir", help="Directory containing source HTML files.")
    source_group.add_argument("--html-files", nargs="+", help="One or more source HTML files.")
    parser.add_argument("--glob", default="*.html", help="Glob used with --source-dir. Default: *.html")
    parser.add_argument("--output-xlsx", required=True, help="Final combined Excel workbook path.")
    parser.add_argument(
        "--work-dir",
        help="Directory for manifests, temporary converted specs, and feature workbooks. Default: _work next to the output workbook.",
    )
    parser.add_argument(
        "--workbook-layout",
        choices=["per_product", "single_sheet_summary"],
        default="single_sheet_summary",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary converted text and feature workbooks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CONFIGS[args.config]
    scripts_dir = Path(__file__).resolve().parent
    output_xlsx = Path(args.output_xlsx).resolve()
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work_dir).resolve() if args.work_dir else output_xlsx.parent / "_work"
    work_root.mkdir(parents=True, exist_ok=True)
    temp_root = work_root / "analysis_output" / f"html_sdw_tmp_{os.getpid()}_{int(time.time())}"
    manifest_json = work_root / "manifests" / f"{output_xlsx.stem}.json"
    text_dir = temp_root / "text"

    html_paths = collect_html_paths(args.source_dir, args.glob, args.html_files)
    print(config["title"])
    print(f"HTML files: {len(html_paths)}")
    print(f"Output: {output_xlsx}")

    converted = convert_html_sources(html_paths, text_dir)
    temp_root.mkdir(parents=True, exist_ok=True)
    (temp_root / "html_conversion_manifest.json").write_text(
        json.dumps({"converted": converted}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    feature_outputs: list[tuple[str, Path]] = []
    try:
        for feature_name, script_name, runtime_dir_name, generated_dir_name, temp_file_name in config["features"]:  # type: ignore[index]
            temp_output = temp_root / str(temp_file_name)
            run_feature(
                scripts_dir,
                str(feature_name),
                str(script_name),
                text_dir,
                temp_output,
                args.workbook_layout,
                work_root / "analysis_output" / str(runtime_dir_name),
                work_root / "analysis_output" / str(generated_dir_name),
            )
            feature_outputs.append((str(feature_name), temp_output))

        merge_features(scripts_dir, output_xlsx, feature_outputs, manifest_json)
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
