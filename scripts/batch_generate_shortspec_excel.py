from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape


DEFAULT_MODEL = "gpt-5.4"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_MAX_OUTPUT_TOKENS = 6000
DEFAULT_TIMEOUT_SECONDS = 300
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
TOP_LEVEL_FEATURES = {
    "PERFORMANCE",
    "DESIGN",
    "CONNECTIVITY",
    "SECURITY & PRIVACY",
    "MANAGEABILITY",
    "ENVIRONMENTAL",
    "ACCESSORIES",
    "CERTIFICATIONS",
}
L2_FEATURES = {
    "Processor",
    "AI PC Category",
    "NPU",
    "Operating System",
    "Graphics",
    "Memory",
    "Storage",
    "Audio",
    "Camera",
    "Camera*",
    "Sensors",
    "Sensors*",
    "Battery",
    "Charging Time",
    "Power Adapter",
    "Power Adapter*",
    "Display",
    "Screen-to-Body Ratio",
    "Multi-mode",
    "Pen",
    "Keyboard",
    "Touchpad",
    "Dimensions (WxDxH)",
    "Weight",
    "Color",
    "Case Material",
    "Buttons",
    "Ethernet",
    "WLAN + Bluetooth",
    "WWAN",
    "WWAN*",
    "Cellular Bands",
    "NFC",
    "Wi-Fi Direct",
    "Wi-Fi Display",
    "Location Services",
    "Ports",
    "Docking",
    "Security",
    "System Management",
    "Bundled Accessories",
    "Bundled Accessories*",
    "Material",
    "Green Certifications",
    "Green Certifications*",
    "Other Certifications",
}


@dataclass
class ProductSpec:
    product: str
    display_name: str
    source_path: Path
    spec_text: str


@dataclass
class GenerationResult:
    product: str
    source_path: str
    mode: str
    shortdesc_text: str
    usage: dict | None
    response_id: str | None
    error: str | None = None


WORD_VBS_EXTRACTOR = r"""
Option Explicit

Const ForReading = 1
Const TristateTrue = -1
Const adTypeText = 2
Const adSaveCreateOverWrite = 2

Dim word
Set word = Nothing

Sub Fail(message)
    WScript.StdErr.WriteLine message
    On Error Resume Next
    If Not word Is Nothing Then word.Quit
    WScript.Quit 1
End Sub

Function NormalizeText(text)
    text = Replace(text, vbCrLf, vbLf)
    text = Replace(text, vbCr, vbLf)
    text = Replace(text, Chr(7), "")
    text = Replace(text, Chr(12), vbLf)
    NormalizeText = text
End Function

Function ReadUnicodeLines(path)
    Dim fso, handle, content
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set handle = fso.OpenTextFile(path, ForReading, False, TristateTrue)
    content = handle.ReadAll
    handle.Close
    content = Replace(content, vbCrLf, vbLf)
    content = Replace(content, vbCr, vbLf)
    ReadUnicodeLines = Split(content, vbLf)
End Function

Sub WriteUtf8(path, text)
    Dim stream
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = adTypeText
    stream.Charset = "utf-8"
    stream.Open
    stream.WriteText text
    stream.SaveToFile path, adSaveCreateOverWrite
    stream.Close
End Sub

If WScript.Arguments.Count < 2 Then
    Fail "Usage: cscript extract_selected_pdf_text.vbs <pdf-list-utf16.txt> <out-dir>"
End If

Dim listPath, outDir, fso
listPath = WScript.Arguments.Item(0)
outDir = WScript.Arguments.Item(1)
Set fso = CreateObject("Scripting.FileSystemObject")

On Error Resume Next
Set word = CreateObject("Word.Application")
If Err.Number <> 0 Then
    Dim createError
    createError = Err.Description
    Err.Clear
    On Error GoTo 0
    Fail "Microsoft Word is required for PDF text extraction. " & createError
End If
On Error GoTo 0

word.Visible = False
word.DisplayAlerts = 0

Dim lines, i, pdfPath, doc, text, outFile, startedAt, elapsed, fileName, errText
lines = ReadUnicodeLines(listPath)

For i = 0 To UBound(lines)
    pdfPath = Trim(lines(i))
    If Len(pdfPath) > 0 Then
        Set doc = Nothing
        startedAt = Timer
        On Error Resume Next
        Set doc = word.Documents.Open(pdfPath, False, True)
        If Err.Number <> 0 Then
            errText = Err.Description
            Err.Clear
            On Error GoTo 0
            Fail "Failed to open PDF: " & pdfPath & " -- " & errText
        End If

        text = NormalizeText(doc.Content.Text)
        If Err.Number <> 0 Then
            errText = Err.Description
            Err.Clear
            On Error GoTo 0
            Fail "Failed to read PDF text: " & pdfPath & " -- " & errText
        End If
        On Error GoTo 0

        fileName = fso.GetFileName(pdfPath)
        outFile = fso.BuildPath(outDir, fileName & ".txt")
        WriteUtf8 outFile, text
        doc.Close False
        Set doc = Nothing

        elapsed = Timer - startedAt
        If elapsed < 0 Then elapsed = elapsed + 86400
        WScript.Echo "EXTRACTED" & vbTab & fileName & vbTab & Len(text) & vbTab & Round(elapsed, 2)
    End If
Next

word.Quit
Set word = Nothing
WScript.Quit 0
""".strip()


def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\x07", "")
    text = text.replace("\x0c", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def derive_product_name(path: Path) -> str:
    base = path.stem
    if base.lower().endswith("_spec"):
        return base[:-5]
    return base


def derive_display_name(path: Path) -> str:
    name = derive_product_name(path)
    if "_" not in name:
        display = re.sub(r"\s+", " ", name).strip()
    else:
        display = name.replace("_", " ")
        display = re.sub(r"\b2 in 1\b", "2-in-1", display, flags=re.I)
        display = re.sub(r"\s+", " ", display).strip()
    if display.startswith("ThinkPad ") and "(" not in display:
        display = re.sub(r"^(ThinkPad .+)\s+(Intel|AMD)$", r"\1 (\2)", display)
    return display


def collect_spec_paths(spec_pdfs: list[str] | None, spec_dir: str | None, glob_pattern: str) -> list[Path]:
    paths: list[Path] = []
    if spec_pdfs:
        for item in spec_pdfs:
            paths.append(Path(item).resolve())
    if spec_dir:
        paths.extend(sorted(Path(spec_dir).resolve().glob(glob_pattern)))

    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path)] = path

    resolved = list(unique.values())
    if not resolved:
        raise SystemExit("No spec files found.")

    for path in resolved:
        if not path.exists():
            raise SystemExit(f"Spec file does not exist: {path}")

    return resolved


def extract_pdf_texts(pdf_paths: list[Path], out_dir: Path, manifest_path: Path) -> dict[Path, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = out_dir.parent / "runtime_spec_pdf_list.txt"
    script_path = out_dir.parent / "extract_selected_pdf_text.vbs"
    list_path.write_text("\n".join(str(path) for path in pdf_paths) + "\n", encoding="utf-16")
    script_path.write_text(WORD_VBS_EXTRACTOR, encoding="utf-8")

    command = [
        "cscript.exe",
        "//nologo",
        str(script_path),
        str(list_path),
        str(out_dir),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, errors="replace")
    except FileNotFoundError as exc:
        raise RuntimeError("cscript.exe was not found. Windows Script Host is required for PDF extraction.") from exc
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout.strip())
        if exc.stderr:
            print(exc.stderr.strip(), file=sys.stderr)
        raise RuntimeError(
            "PDF text extraction failed. Microsoft Word and Windows Script Host are required on the target machine."
        ) from exc
    finally:
        list_path.unlink(missing_ok=True)
        script_path.unlink(missing_ok=True)
    if completed.stdout:
        print(completed.stdout.strip())
    if completed.stderr:
        print(completed.stderr.strip(), file=sys.stderr)

    by_source: dict[Path, str] = {}
    extractions: list[dict[str, object]] = []
    for path in pdf_paths:
        output_txt = out_dir / f"{path.name}.txt"
        if not output_txt.exists():
            raise RuntimeError(f"PDF text extraction did not create expected text file: {output_txt}")
        text = normalize_text(output_txt.read_text(encoding="utf-8-sig"))
        resolved = path.resolve()
        by_source[resolved] = text
        extractions.append(
            {
                "source_pdf": str(resolved),
                "file_name": path.name,
                "product": derive_product_name(path),
                "output_txt": str(output_txt.resolve()),
                "char_count": len(text),
            }
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir.resolve()),
        "pdf_count": len(pdf_paths),
        "extractions": extractions,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return by_source


def load_product_specs(paths: list[Path], runtime_text_dir: Path, runtime_manifest: Path) -> list[ProductSpec]:
    pdf_paths = [path for path in paths if path.suffix.lower() == ".pdf"]
    txt_map: dict[Path, str] = {}
    if pdf_paths:
        missing_pdf_paths: list[Path] = []
        for path in pdf_paths:
            cache_path = runtime_text_dir / f"{path.name}.txt"
            resolved = path.resolve()
            if cache_path.exists():
                txt_map[resolved] = normalize_text(cache_path.read_text(encoding="utf-8-sig"))
            else:
                missing_pdf_paths.append(path)
        if missing_pdf_paths:
            txt_map.update(extract_pdf_texts(missing_pdf_paths, runtime_text_dir, runtime_manifest))

    products: list[ProductSpec] = []
    for path in paths:
        if path.suffix.lower() == ".pdf":
            spec_text = txt_map[path.resolve()]
        else:
            spec_text = normalize_text(path.read_text(encoding="utf-8"))
        products.append(
            ProductSpec(
                product=derive_product_name(path),
                display_name=derive_display_name(path),
                source_path=path,
                spec_text=spec_text,
            )
        )
    return products


def load_prompt(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8").strip()


def build_response_request(
    model: str,
    system_prompt: str,
    spec_text: str,
    reasoning_effort: str,
    max_output_tokens: int,
) -> dict:
    return {
        "model": model,
        "instructions": system_prompt,
        "input": spec_text,
        "reasoning": {
            "effort": reasoning_effort,
        },
        "max_output_tokens": max_output_tokens,
        "text": {
            "format": {
                "type": "text",
            }
        },
    }


def call_responses_api(
    api_key: str,
    request_body: dict,
    timeout_seconds: int,
) -> dict:
    body = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        url="https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Responses API HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Responses API connection error: {exc}") from exc


def extract_output_text(response_json: dict) -> str:
    parts: list[str] = []
    for item in response_json.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))

    text = "\n".join(part for part in parts if part).strip()
    if not text:
        raise RuntimeError("Model response did not contain any output_text content.")
    return text


def load_mock_shortdesc(product: str, mock_dir: Path) -> str:
    candidates = [
        mock_dir / f"{product}_ShortDesc_AutoLayout.pdf.txt",
        mock_dir / f"{product}_ShortDesc_AutoLayout.txt",
        mock_dir / f"{product}.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return normalize_text(candidate.read_text(encoding="utf-8")).strip()
    raise FileNotFoundError(f"No mock shortdesc text found for product {product} in {mock_dir}")


def make_error_sheet_text(product: str, error: str) -> str:
    return f"ERROR\nProduct\n{product}\nDetails\n{error}"


def sanitize_sheet_name(name: str, taken: set[str]) -> str:
    cleaned = INVALID_SHEET_CHARS.sub("_", name).strip()
    if not cleaned:
        cleaned = "Sheet"
    cleaned = cleaned[:31]
    candidate = cleaned
    index = 2
    while candidate in taken:
        suffix = f"_{index}"
        candidate = f"{cleaned[:31 - len(suffix)]}{suffix}"
        index += 1
    taken.add(candidate)
    return candidate


def excel_column_name(index: int) -> str:
    result = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def normalize_feature_label(label: str) -> str:
    return re.sub(r"\*+$", "", label).strip()


def shortdesc_text_to_feature_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if text.startswith("ERROR\n"):
        detail_lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in detail_lines[1:]:
            rows.append(("ERROR", "Details", line))
        return rows

    current_l1 = ""
    current_l2 = ""

    for raw_line in text.splitlines():
        line = normalize_text(raw_line).strip()
        if not line:
            continue
        if line in {"PSREF", "Product Specifications", "Reference"}:
            continue
        if line == "Note:":
            break
        if line in {"MIL-STD-810H", "MIL-STD-810G"}:
            if current_l1 == "CERTIFICATIONS":
                target_l2 = current_l2 if current_l2 == "Other Certifications" else "Other Certifications"
                rows.append((current_l1, target_l2, line))
            else:
                rows.append(("CERTIFICATIONS", "Other Certifications", line))
            continue
        if line in TOP_LEVEL_FEATURES:
            current_l1 = line
            current_l2 = ""
            continue
        if line in L2_FEATURES:
            current_l2 = normalize_feature_label(line)
            continue
        if current_l1:
            rows.append((current_l1, current_l2, line))

    return rows


def render_short_spec_cell(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return "\n".join(f"- {value}" for value in cleaned)


def aggregate_feature_rows(feature_rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    grouped: list[tuple[str, str, list[str]]] = []
    index_by_key: dict[tuple[str, str], int] = {}

    for l1_feature, l2_feature, short_spec in feature_rows:
        key = (l1_feature, l2_feature)
        if key not in index_by_key:
            index_by_key[key] = len(grouped)
            grouped.append((l1_feature, l2_feature, [short_spec]))
            continue
        grouped[index_by_key[key]][2].append(short_spec)

    return [
        (l1_feature, l2_feature, render_short_spec_cell(short_specs))
        for l1_feature, l2_feature, short_specs in grouped
    ]


def shortdesc_text_to_table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = [["L1 Feature", "L2 Feature", "Short Spec"]]
    for l1_feature, l2_feature, short_spec in aggregate_feature_rows(shortdesc_text_to_feature_rows(text)):
        rows.append([l1_feature, l2_feature, short_spec])
    return rows


def build_summary_table_rows(sheets: list[tuple[str, str | list[list[str]]]]) -> list[list[str]]:
    rows: list[list[str]] = [["Product", "L1 Feature", "L2 Feature", "Short Spec"]]
    for product, payload in sheets:
        if isinstance(payload, str):
            feature_rows = aggregate_feature_rows(shortdesc_text_to_feature_rows(payload))
        else:
            feature_rows = aggregate_feature_rows(
                [
                    (row[0] if len(row) > 0 else "", row[1] if len(row) > 1 else "", row[2] if len(row) > 2 else "")
                    for row in payload[1:]
                ]
            )
        for l1_feature, l2_feature, short_spec in feature_rows:
            rows.append([product, l1_feature, l2_feature, short_spec])
    return rows


def build_sheet_xml(rows_data: list[list[str]]) -> str:
    rows: list[str] = []
    max_cols = max((len(row) for row in rows_data), default=1)
    for row_number, row_values in enumerate(rows_data, start=1):
        cells: list[str] = []
        for col_number, value in enumerate(row_values, start=1):
            cell_ref = f"{excel_column_name(col_number)}{row_number}"
            if value:
                cells.append(
                    f'<c r="{cell_ref}" s="0" t="inlineStr">'
                    f'<is><t xml:space="preserve">{escape(value)}</t></is>'
                    f"</c>"
                )
        if cells:
            rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
        else:
            rows.append(f'<row r="{row_number}"/>')

    col_widths = [36, 28, 28, 120]
    col_defs: list[str] = []
    for index in range(1, max_cols + 1):
        width = col_widths[index - 1] if index <= len(col_widths) else 60
        col_defs.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        f'<cols>{"".join(col_defs)}</cols>'
        f'<sheetData>{"".join(rows)}</sheetData>'
        '</worksheet>'
    )


def write_xlsx(
    workbook_path: Path,
    sheets: list[tuple[str, str | list[list[str]]]],
    workbook_layout: str = "per_product",
) -> None:
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    taken: set[str] = set()
    sheet_entries: list[tuple[str, str, list[list[str]]]] = []
    if workbook_layout == "single_sheet_summary":
        summary_name = sanitize_sheet_name("All Products", taken)
        sheet_entries.append((summary_name, "sheet1", build_summary_table_rows(sheets)))
    else:
        for index, (proposed_name, payload) in enumerate(sheets, start=1):
            sheet_name = sanitize_sheet_name(proposed_name, taken)
            if isinstance(payload, str):
                sheet_rows = shortdesc_text_to_table_rows(payload)
            else:
                sheet_rows = payload
            sheet_entries.append((sheet_name, f"sheet{index}", sheet_rows))

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for _, sheet_file, _ in sheet_entries:
        content_types.append(
            f'<Override PartName="/xl/worksheets/{sheet_file}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    content_types.append("</Types>")

    workbook_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        '<bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>',
        "<sheets>",
    ]
    for index, (sheet_name, _, _) in enumerate(sheet_entries, start=1):
        workbook_xml.append(
            f'<sheet name="{escape(sheet_name)}" sheetId="{index}" r:id="rId{index}"/>'
        )
    workbook_xml.append("</sheets></workbook>")

    workbook_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for index, (_, sheet_file, _) in enumerate(sheet_entries, start=1):
        workbook_rels.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/{sheet_file}.xml"/>'
        )
    workbook_rels.append(
        f'<Relationship Id="rId{len(sheet_entries) + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    workbook_rels.append("</Relationships>")

    package_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1"/></xf></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )

    with zipfile.ZipFile(workbook_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "".join(content_types))
        zf.writestr("_rels/.rels", package_rels)
        zf.writestr("xl/workbook.xml", "".join(workbook_xml))
        zf.writestr("xl/_rels/workbook.xml.rels", "".join(workbook_rels))
        zf.writestr("xl/styles.xml", styles_xml)
        for _, sheet_file, rows_data in sheet_entries:
            zf.writestr(f"xl/worksheets/{sheet_file}.xml", build_sheet_xml(rows_data))


def save_generation_texts(results: Iterable[GenerationResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        suffix = "_error" if result.error else ""
        target = out_dir / f"{result.product}{suffix}.txt"
        target.write_text(result.shortdesc_text, encoding="utf-8")


def write_manifest(
    results: list[GenerationResult],
    workbook_path: Path,
    model: str,
    prompt_path: Path,
    workbook_layout: str,
) -> None:
    manifest_path = workbook_path.with_suffix(".json")
    payload = {
        "workbook": str(workbook_path),
        "model": model,
        "prompt_file": str(prompt_path),
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
        description="Generate Lenovo short specs for multiple product spec files and save them to one Excel workbook."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--spec-files",
        "--spec-pdfs",
        dest="spec_pdfs",
        nargs="+",
        help="One or more spec PDF/TXT files to process.",
    )
    source_group.add_argument("--spec-dir", help="Directory containing spec files.")
    parser.add_argument("--glob", default="*_Spec.PDF", help="Glob used with --spec-dir. Default: *_Spec.PDF")
    parser.add_argument("--output-xlsx", required=True, help="Path to the output Excel workbook.")
    parser.add_argument(
        "--workbook-layout",
        choices=["per_product", "single_sheet_summary"],
        default="per_product",
        help="Workbook layout. per_product=one worksheet per product; single_sheet_summary=all products in one worksheet.",
    )
    parser.add_argument(
        "--system-prompt-file",
        default="prompts/spec_to_shortdesc_v7_system.txt",
        help="Plain-text system prompt file used for generation.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name passed to the Responses API.")
    parser.add_argument(
        "--reasoning-effort",
        default=DEFAULT_REASONING_EFFORT,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="Reasoning effort for the Responses API.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help=f"Max output tokens. Default: {DEFAULT_MAX_OUTPUT_TOKENS}",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable that contains the OpenAI API key. Default: OPENAI_API_KEY",
    )
    parser.add_argument(
        "--runtime-text-dir",
        default="analysis_output/runtime_spec_text",
        help="Directory used to cache extracted spec text files.",
    )
    parser.add_argument(
        "--generated-text-dir",
        default="analysis_output/generated_shortspec_batch",
        help="Directory used to save generated per-product text outputs.",
    )
    parser.add_argument(
        "--mock-shortdesc-dir",
        help="Offline test mode: load actual shortdesc text files from this directory instead of calling the API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_paths = collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    prompt_path = Path(args.system_prompt_file).resolve()
    if not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")

    runtime_text_dir = Path(args.runtime_text_dir).resolve()
    runtime_manifest = runtime_text_dir.parent / "runtime_spec_text_manifest.json"
    generated_text_dir = Path(args.generated_text_dir).resolve()
    workbook_path = Path(args.output_xlsx).resolve()

    products = load_product_specs(spec_paths, runtime_text_dir, runtime_manifest)
    system_prompt = load_prompt(prompt_path)

    api_key = os.environ.get(args.api_key_env)
    if not args.mock_shortdesc_dir and not api_key:
        raise SystemExit(
            f"{args.api_key_env} is not set. Set it or use --mock-shortdesc-dir for offline validation."
        )

    results: list[GenerationResult] = []
    sheets: list[tuple[str, str]] = []
    mock_dir = Path(args.mock_shortdesc_dir).resolve() if args.mock_shortdesc_dir else None

    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.source_path}")
        try:
            if mock_dir is not None:
                shortdesc_text = load_mock_shortdesc(product.product, mock_dir)
                result = GenerationResult(
                    product=product.product,
                    source_path=str(product.source_path),
                    mode="mock",
                    shortdesc_text=shortdesc_text,
                    usage=None,
                    response_id=None,
                )
            else:
                request_body = build_response_request(
                    model=args.model,
                    system_prompt=system_prompt,
                    spec_text=product.spec_text,
                    reasoning_effort=args.reasoning_effort,
                    max_output_tokens=args.max_output_tokens,
                )
                response_json = call_responses_api(api_key, request_body, args.timeout_seconds)
                shortdesc_text = extract_output_text(response_json)
                result = GenerationResult(
                    product=product.product,
                    source_path=str(product.source_path),
                    mode="responses_api",
                    shortdesc_text=shortdesc_text,
                    usage=response_json.get("usage"),
                    response_id=response_json.get("id"),
                )
        except Exception as exc:
            error_text = str(exc)
            result = GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="error",
                shortdesc_text=make_error_sheet_text(product.product, error_text),
                usage=None,
                response_id=None,
                error=error_text,
            )

        results.append(result)
        sheets.append((product.display_name, result.shortdesc_text))

    save_generation_texts(results, generated_text_dir)
    write_xlsx(workbook_path, sheets, workbook_layout=args.workbook_layout)
    write_manifest(results, workbook_path, args.model, prompt_path, args.workbook_layout)

    failures = [result for result in results if result.error]
    print(f"WORKBOOK\t{workbook_path}")
    print(f"SHEETS\t{len(sheets)}")
    print(f"FAILURES\t{len(failures)}")
    if failures:
        for failure in failures:
            print(f"FAILED\t{failure.product}\t{failure.error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
