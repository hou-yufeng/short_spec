from __future__ import annotations

import argparse
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from batch_generate_shortspec_excel import write_xlsx


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS, "pr": PKG_REL_NS}


def column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref.upper())
    if not match:
        return 1
    value = 0
    for char in match.group(1):
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value


def load_shared_strings(workbook_zip: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    values: list[str] = []
    for item in root.findall("m:si", NS):
        text_parts = [node.text or "" for node in item.findall(".//m:t", NS)]
        values.append("".join(text_parts))
    return values


def cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", NS))

    value_node = cell.find("m:v", NS)
    if value_node is None or value_node.text is None:
        return ""

    if cell_type == "s":
        try:
            return shared_strings[int(value_node.text)]
        except (IndexError, ValueError):
            return ""
    return value_node.text


def relationship_target(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def read_sheet_rows(workbook_zip: zipfile.ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(workbook_zip.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//m:sheetData/m:row", NS):
        values: list[str] = []
        for cell in row.findall("m:c", NS):
            index = column_index(cell.attrib.get("r", "")) - 1
            while len(values) <= index:
                values.append("")
            values[index] = cell_text(cell, shared_strings)
        rows.append(values)
    return rows


def read_workbook_sheets(path: Path) -> list[tuple[str, list[list[str]]]]:
    with zipfile.ZipFile(path) as workbook_zip:
        workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        rels_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
        shared_strings = load_shared_strings(workbook_zip)

        rel_targets = {
            rel.attrib["Id"]: relationship_target(rel.attrib["Target"])
            for rel in rels_root.findall("pr:Relationship", NS)
            if "Id" in rel.attrib and "Target" in rel.attrib
        }

        sheets: list[tuple[str, list[list[str]]]] = []
        for sheet in workbook_root.findall(".//m:sheets/m:sheet", NS):
            name = sheet.attrib.get("name", "Sheet")
            rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
            if not rel_id or rel_id not in rel_targets:
                continue
            sheets.append((name, read_sheet_rows(workbook_zip, rel_targets[rel_id], shared_strings)))
    return sheets


def normalize_short_spec_slash_spacing(value: str) -> str:
    value = re.sub(r"\s*/\s*", " / ", value)
    value = re.sub(r" {2,}", " ", value)
    return value.strip()


def normalize_short_spec_rows(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows

    header = rows[0]
    short_spec_indexes = [
        index
        for index, value in enumerate(header)
        if value.strip().lower() == "short spec"
    ]
    if not short_spec_indexes:
        return rows

    normalized_rows: list[list[str]] = [header]
    for row in rows[1:]:
        normalized = list(row)
        for index in short_spec_indexes:
            if index < len(normalized) and "/" in normalized[index]:
                normalized[index] = normalize_short_spec_slash_spacing(normalized[index])
        normalized_rows.append(normalized)
    return normalized_rows


def build_output_sheets(features: list[tuple[str, Path]]) -> list[tuple[str, list[list[str]]]]:
    output: list[tuple[str, list[list[str]]]] = []
    for feature_name, path in features:
        sheets = read_workbook_sheets(path)
        if len(sheets) == 1:
            output.append((feature_name, normalize_short_spec_rows(sheets[0][1])))
            continue
        for sheet_name, rows in sheets:
            output.append((f"{feature_name} {sheet_name}", normalize_short_spec_rows(rows)))
    return output


def write_manifest(output_path: Path, features: list[tuple[str, Path]], manifest_path: Path | None = None) -> None:
    payload = {
        "workbook": str(output_path),
        "features": [],
    }
    for feature_name, workbook_path in features:
        feature_manifest_path = workbook_path.with_suffix(".json")
        entry: dict[str, object] = {
            "feature": feature_name,
            "workbook": str(workbook_path),
        }
        if feature_manifest_path.exists():
            entry["manifest"] = json.loads(feature_manifest_path.read_text(encoding="utf-8"))
        payload["features"].append(entry)

    target = manifest_path or output_path.with_suffix(".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge feature workbooks into one Excel workbook.")
    parser.add_argument("--output-xlsx", required=True, help="Path to the merged output workbook.")
    parser.add_argument("--manifest-json", help="Optional path for the merge manifest JSON.")
    parser.add_argument(
        "--feature",
        action="append",
        nargs=2,
        metavar=("NAME", "XLSX"),
        required=True,
        help="Feature display name and source workbook path. Repeat for each feature.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output_xlsx).resolve()
    manifest_path = Path(args.manifest_json).resolve() if args.manifest_json else None
    features = [(name, Path(path).resolve()) for name, path in args.feature]
    missing = [str(path) for _, path in features if not path.exists()]
    if missing:
        raise SystemExit("Missing feature workbook(s): " + "; ".join(missing))

    sheets = build_output_sheets(features)
    if not sheets:
        raise SystemExit("No worksheets found in feature workbooks.")

    write_xlsx(output_path, sheets, workbook_layout="per_product")
    write_manifest(output_path, features, manifest_path)
    print(f"WORKBOOK\t{output_path}")
    print(f"SHEETS\t{len(sheets)}")


if __name__ == "__main__":
    main()
