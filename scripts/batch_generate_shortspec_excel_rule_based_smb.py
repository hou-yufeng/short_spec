from __future__ import annotations

import argparse
import re
from pathlib import Path

import batch_generate_shortspec_excel_rule_based_consumer as base


_ORIG_NORMALIZE_PROCESSOR_FAMILY_PHRASE = base.normalize_processor_family_phrase
_ORIG_SUMMARIZE_CASE_MATERIAL = base.summarize_case_material
_ORIG_EXTRACT_PROCESSOR = base.extract_processor


def normalize_processor_family_phrase_smb(line: str) -> str:
    line = _ORIG_NORMALIZE_PROCESSOR_FAMILY_PHRASE(line)
    line = re.sub(r"\bIntel Core Ultra ([3579]) ([0-9]+)H\b", r"Intel H Series Core Ultra \1 Processor (Series 1)", line, flags=re.I)
    line = re.sub(r"\bIntel Core Ultra ([579]) ([0-9]+)\b", r"Intel Core Ultra \1 Processor (Series 1)", line, flags=re.I)
    line = re.sub(
        r"\bIntel Core ([3579]) ([0-9]+)\b",
        lambda m: f"Intel Core {m.group(1)} Processor (Series 1)" if int(m.group(2)) < 100 else m.group(0),
        line,
        flags=re.I,
    )
    line = re.sub(
        r"^(\d+(?:st|nd|rd|th) Gen Intel (?:U(?:,\s*P(?:\s*or\s*H)?)?|U\s*or\s*P|P|H|HX|U,\s*P\s*or\s*H)\s+Series Core .+?) Processor$",
        r"\1",
        line,
        flags=re.I,
    )
    line = re.sub(
        r"^(AMD Ryzen(?: AI)? (?:3|5|7|9)(?:\s*/\s*(?:3|5|7|9))*?) Processor$",
        r"\1",
        line,
        flags=re.I,
    )
    line = re.sub(r"\bProcessor \(Series ([123])\)\b", r"Processor (Series \1)", line, flags=re.I)
    return re.sub(r"\s+", " ", line).strip(" ,;.")


def _infer_smb_intel_series(perf: list[str]) -> str:
    blob = " ".join(perf)
    suffixes = re.findall(
        r"\b(?:Core i\d|Core Ultra \d|Intel Processor)\s*-?\d*[A-Z]*([UPHNX]{1,2})\b",
        blob,
        flags=re.I,
    )
    normalized = [suffix.upper() for suffix in suffixes if suffix.upper() in {"U", "P", "H", "HX", "N"}]
    if not normalized:
        return ""
    if len(set(normalized)) == 1:
        return normalized[0]
    return ""


def extract_processor_smb(perf: list[str]) -> list[str]:
    stop_labels = [
        "Processor**",
        "AI (Artificial Intelligence)",
        "Operating System",
        "Operating System**",
        "Graphics",
        "Chipset",
        "Memory",
    ]
    block = base.slice_after_exact_label(perf, ["Processor Family"], stop_labels)
    if not block:
        block = base.slice_after_exact_label(perf, ["Processor"], stop_labels)

    lines: list[str] = []
    raw_keys: list[str] = []
    for line in block:
        lowered = line.lower()
        if base.is_noise_line(line):
            continue
        if base.normalize_label_token(line) in {
            "processor family",
            "processor",
            "processor name",
            "cores",
            "threads",
            "base frequency",
            "max frequency",
            "cache",
            "processor graphics",
            "npu",
            "overall tops",
            "memory support",
        }:
            continue
        if any(token in lowered for token in ["operating system", "graphics", "memory"]):
            continue
        if "processor" not in lowered:
            continue
        normalized = base.normalize_processor_summary(line)
        if normalized:
            lines.append(normalized)
            raw_keys.append(base.normalize_compare_key(line))

    normalized_lines = base.unique_preserve(lines)
    generic_only = raw_keys and all(key in base.PROCESSOR_GENERIC_FAMILY_PATTERNS for key in raw_keys)

    name_start = base.find_exact_index(perf, ["Processor Name"])
    if name_start is None:
        for idx in range(len(perf) - 1):
            if base.normalize_label_token(perf[idx]) == "processor" and base.normalize_label_token(perf[idx + 1]) == "name":
                name_start = idx + 1
                break
    name_candidates: list[str] = []
    if name_start is not None:
        scan_block = perf[name_start + 1 : min(len(perf), name_start + 50)]
        for index, line in enumerate(scan_block):
            lowered = line.lower()
            if base.is_noise_line(line):
                continue
            if base.normalize_label_token(line) in {"operating system", "graphics", "chipset", "memory"}:
                break
            if base.normalize_label_token(line) in {
                "processor name",
                "cores",
                "threads",
                "base frequency",
                "max frequency",
                "cache",
                "processor graphics",
                "operating system",
                "npu",
                "overall tops",
                "memory support",
            }:
                continue
            if not re.search(r"[A-Za-z]", line):
                continue
            if re.match(r"^\d+x\b", line) or re.match(r"^\d+\s*\(", line) or re.fullmatch(r"\d+", line):
                continue
            if any(token in lowered for token in ["ghz", "thread", "cache", "graphics", " gpu", "mali"]):
                continue
            if any(token in lowered for token in ["p-core", "e-core", "intel iris xe", "intel uhd"]):
                continue
            if re.search(r"\b\d+mb\b", lowered):
                continue
            normalized = base.normalize_processor_name_candidate(line)
            if normalized.lower().startswith("mediatek "):
                next_line = scan_block[index + 1] if index + 1 < len(scan_block) else ""
                if "octa-core" in next_line.lower():
                    normalized = f"{normalized}, Octa-core"
            if normalized:
                name_candidates.append(normalized)

    inferred_series = _infer_smb_intel_series(perf)
    if inferred_series:
        normalized_lines = [base.apply_inferred_intel_series(line, inferred_series) for line in normalized_lines]
    out: list[str] = []
    for line in normalized_lines:
        if inferred_series and "series" not in line.lower():
            line = re.sub(
                r"^(\d+(?:st|nd|rd|th) Gen Intel) Core (.+)$",
                rf"\1 {inferred_series} Series Core \2",
                line,
                flags=re.I,
            )
            line = re.sub(
                r"^(\d+(?:st|nd|rd|th) Generation Intel) Core (.+)$",
                rf"\1 {inferred_series} Series Core \2",
                line,
                flags=re.I,
            )
        line = normalize_processor_family_phrase_smb(line)
        out.append(line)

    if generic_only and name_candidates:
        generic_names: list[str] = []
        for line in name_candidates:
            lowered = line.lower()
            if lowered.startswith("qualcomm snapdragon"):
                generic_names.append(line)
                continue
            if lowered.startswith("mediatek "):
                generic_names.append(line)
        if generic_names:
            return base.unique_preserve(generic_names[:4])

    return base.unique_preserve(out[:5])


def _normalize_wifi_fragment(line: str) -> str:
    line = base.clean_line(line)
    line = re.sub(r",?\s*(?:M\.2\s+card|CNVi|PCIe card)\b", "", line, flags=re.I)
    line = re.sub(r",?\s*Intel vPro(?: technology)? support\b", "", line, flags=re.I)
    line = re.sub(r"\b2x2\s+Wi-?Fi\b", "", line, flags=re.I)
    line = re.sub(r"\s+", " ", line).strip(" ,")
    return line


def _format_wifi_standard(line: str) -> str:
    standard_match = re.search(r"802\.11([a-z0-9]+)", line, re.I)
    wifi_match = re.search(r"Wi-?Fi\s*(7|6E|6|5)", line, re.I)
    if standard_match and wifi_match:
        return f"802.11{standard_match.group(1).lower()} (Wi-Fi {wifi_match.group(1).upper()})"
    if standard_match:
        return f"802.11{standard_match.group(1).lower()}"
    if wifi_match:
        return f"Wi-Fi {wifi_match.group(1).upper()}"
    return ""


def _format_bluetooth(line: str) -> str:
    match = re.search(r"Bluetooth\s*([0-9.]+(?:\s*or\s*[0-9.]+)*(?:\s*,\s*[0-9.]+(?:\s*or\s*[0-9.]+)*)*)", line, re.I)
    if not match:
        return ""
    return f"Bluetooth {re.sub(r'\\s+', ' ', match.group(1)).strip()}"


def summarize_wlan_smb(conn: list[str]) -> list[str]:
    lines = base.slice_after_exact_label(
        conn,
        ["WLAN + Bluetooth", "WLAN + Bluetooth[1]", "WLAN + Bluetooth**"],
        ["WWAN", "WWAN**", "SIM Card", "Ethernet", "NFC", "Ports"],
    )
    wifi_only: list[str] = []
    bluetooth_only: list[str] = []
    combined: list[str] = []
    vendor_lines: list[str] = []
    for raw_line in lines:
        line = _normalize_wifi_fragment(raw_line)
        lowered = line.lower()
        if not line or base.is_noise_line(line):
            continue
        if base.normalize_label_token(line) == "wlan + bluetooth":
            continue
        if "subject to the regulatory requirements" in lowered:
            continue
        if "support information" in lowered or "platform require" in lowered or "platform requires" in lowered:
            continue

        has_wifi = bool(re.search(r"802\.11|Wi-?Fi", line, re.I))
        has_bt = "bluetooth" in lowered
        vendorish = any(token in lowered for token in ["intel ", "qualcomm", "mediatek", "killer", "realtek"]) and "802.11" not in lowered
        if vendorish and has_bt:
            vendor_lines.append(line)
            continue
        if has_wifi and has_bt:
            wifi_part = _format_wifi_standard(line)
            bt_part = _format_bluetooth(line)
            if wifi_part and bt_part:
                combined.append(f"{wifi_part}, {bt_part}")
            else:
                combined.append(line)
            continue
        if has_wifi:
            formatted = _format_wifi_standard(line)
            wifi_only.append(formatted or line)
            continue
        if has_bt:
            bluetooth_only.append(_format_bluetooth(line) or line)

    if wifi_only and bluetooth_only:
        primary_bt = bluetooth_only[0]
        for wifi_part in wifi_only:
            combined.append(f"{wifi_part}, {primary_bt}")
    else:
        combined.extend(wifi_only)
        combined.extend(bluetooth_only)

    out = base.unique_preserve(vendor_lines + combined)
    return out[:4]


def summarize_security_smb(sec: list[str]) -> list[str]:
    out: list[str] = []
    security_chip = base.slice_after_exact_label(
        sec,
        ["Security Chip"],
        ["Fingerprint Reader", "BIOS Security", "Other Security", "MANAGEABILITY", "ENVIRONMENTAL", "CERTIFICATIONS", "SERVICE"],
    )
    fingerprint = base.slice_after_exact_label(
        sec,
        ["Fingerprint Reader"],
        ["BIOS Security", "Other Security", "MANAGEABILITY", "ENVIRONMENTAL", "CERTIFICATIONS", "SERVICE"],
    )
    other_security = base.slice_after_exact_label(
        sec,
        ["Other Security"],
        ["MANAGEABILITY", "ENVIRONMENTAL", "CERTIFICATIONS", "SERVICE"],
    )

    for line in security_chip:
        lowered = line.lower()
        if "firmware tpm 2.0" in lowered:
            out.append("Firmware TPM 2.0")
        elif "discrete tpm 2.0" in lowered:
            out.append("Discrete TPM 2.0" + ("*" if "*" in line else ""))
        elif "microsoft pluton" in lowered and "tpm" in lowered:
            out.append("Microsoft Pluton TPM 2.0")
        elif "google security chip h1" in lowered:
            out.append("Google Security Chip H1")

    for line in sec:
        lowered = line.lower()
        if "kensington" in lowered and "nano" in lowered:
            out.append("Kensington Nano Security Slot")
            break
        if "kensington security slot" in lowered:
            out.append("Kensington Security Slot")
            break

    for line in fingerprint:
        lowered = line.lower()
        if lowered.startswith("no "):
            continue
        optional = "*" if "*" in line or "(optional)" in lowered else ""
        if "fingerprint" not in lowered:
            continue
        if "smart power button" in lowered and "match-on-chip" in lowered:
            out.append(f"Touch style MOC fingerprint reader on smart power button{optional}")
            break
        if "smart power button" in lowered:
            out.append(f"Touch style fingerprint reader on smart power button{optional}")
            break
        if "side power button" in lowered and "match-on-chip" in lowered:
            out.append(f"Touch style MOC fingerprint reader on side power button{optional}")
            break
        if "side power button" in lowered:
            out.append(f"Touch style fingerprint reader on side power button{optional}")
            break
        if "power button" in lowered and "match-on-chip" in lowered:
            out.append(f"Touch style MOC fingerprint reader on power button{optional}")
            break
        if "power button" in lowered:
            out.append(f"Touch style fingerprint reader on power button{optional}")
            break
        if "match-on-chip" in lowered:
            out.append(f"Touch style MOC fingerprint reader{optional}")
            break
        if "touch style" in lowered:
            out.append(f"Touch style fingerprint reader{optional}")
            break
        out.append("Fingerprint reader" + optional)
        break

    for line in other_security:
        lowered = line.lower()
        optional = "*" if "*" in line or "(optional)" in lowered else ""
        if "camera privacy shutter" in lowered:
            out.append("Camera privacy shutter")
        elif re.search(r"\be-shutter\b", lowered):
            out.append("E-shutter")
        elif "windows hello" in lowered:
            out.append(f"IR camera for Windows Hello (facial recognition){optional}")
        elif "privacy guard with privacy alert" in lowered:
            out.append("Privacy Guard with Privacy Alert")

    return base.unique_preserve(out)


def summarize_screen_to_body_smb(design: list[str]) -> list[str]:
    lines = base.slice_after_exact_label(design, ["Screen-to-Body Ratio"], ["Multi-mode", "Input Device", "Pen", "Keyboard"])
    filtered = [line for line in lines if "%" in line and not base.is_noise_line(line)]
    return base.unique_preserve(filtered[:6])


def summarize_case_material_smb(design: list[str]) -> list[str]:
    values = _ORIG_SUMMARIZE_CASE_MATERIAL(design)
    out: list[str] = []
    for line in values:
        line = re.sub(r",?\s*glass\s*\(display cover\)", "", line, flags=re.I)
        line = re.sub(r"\baluminium unibody cnc\b", "aluminium", line, flags=re.I)
        line = re.sub(r"\baluminum unibody cnc\b", "aluminium", line, flags=re.I)
        line = re.sub(r"\baluminium stamping\b", "aluminium", line, flags=re.I)
        line = re.sub(r"\baluminum stamping\b", "aluminium", line, flags=re.I)
        line = re.sub(r"\baluminum\b", "aluminium", line, flags=re.I)
        line = re.sub(r"\s+", " ", line).strip(" ,")
        line = line.replace(") aluminium (", "), aluminium (")
        if line:
            out.append(line)
    return base.unique_preserve(out[:4])


def summarize_power_adapter_smb(perf: list[str]) -> tuple[str, list[str]]:
    lines = base.slice_after_exact_label(perf, ["Power Adapter", "Power Adapter**"], ["DESIGN", "Display"])
    out: list[str] = []
    optional = False
    for line in lines:
        lowered = line.lower()
        if base.is_noise_line(line):
            continue
        if base.normalize_label_token(line) == "power adapter":
            continue
        if lowered.startswith("no power adapter"):
            optional = True
            continue
        if "offerings depend on the country" in lowered:
            continue
        if "adapter" not in lowered:
            continue
        normalized = base.normalize_power_adapter_line(line)
        if "supports pd 3.0" in lowered and "pd 3.0" not in normalized.lower():
            normalized = f"{normalized}, PD 3.0"
        out.append(normalized)
    return ("Power Adapter*" if optional else "Power Adapter"), base.unique_preserve(out)


def summarize_ports_smb(conn: list[str]) -> list[str]:
    lines = base.slice_after_label(conn, ["Ports", "Ports[1]"], ["Docking"])
    out: list[str] = []
    optional_mode = False
    for raw_line in lines:
        lowered = raw_line.lower()
        normalized = base.normalize_label_token(raw_line)
        if normalized in {"standard ports", "optional ports"}:
            optional_mode = normalized.startswith("optional")
            continue
        if "transfer speed of the ports" in lowered:
            continue
        fragments = [part.strip() for part in raw_line.split("•") if part.strip()]
        for line in fragments:
            if not (line.startswith("1x") or line.startswith("2x")):
                continue
            rendered = base.normalize_port_line(line)
            rendered = re.sub(r"\s*&\s*", ", ", rendered)
            rendered = re.sub(r"\bdata transfer\b", "data", rendered, flags=re.I)
            rendered = re.sub(r"\bDisplayPort\b", "DP", rendered, flags=re.I)
            rendered = re.sub(r"\bPower Delivery\b", "PD", rendered, flags=re.I)
            rendered = re.sub(r"\bDPTM?\s*1\.4\b", "DP 1.4", rendered, flags=re.I)
            rendered = re.sub(r",\s*,+", ", ", rendered).strip()
            rendered = re.sub(r"\*+$", "", rendered)
            if optional_mode:
                rendered = f"{rendered}*"
            out.append(rendered)
    return base.unique_preserve(out)


def summarize_memory_smb(perf: list[str]) -> list[str]:
    max_lines = base.slice_after_exact_label(perf, ["Max Memory", "Max Memory[1]"], ["Memory Slots", "Memory Type", "Storage"])
    slot_lines = base.slice_after_exact_label(perf, ["Memory Slots"], ["Memory Type", "Storage"])
    type_lines = base.slice_after_exact_label(perf, ["Memory Type"], ["Storage", "Removable Storage"])
    if not type_lines:
        for line in perf:
            if line.lower().startswith("memory type "):
                type_lines = [re.sub(r"^Memory Type\s*", "", line, flags=re.I).strip()]
                break

    max_lines = [
        line
        for line in max_lines
        if "based on the technical readiness" not in line.lower()
        and "based on the test results" not in line.lower()
        and base.normalize_label_token(line) not in {"max memory", "memory slots", "memory type"}
        and not base.is_noise_line(line)
    ]
    slot_line = slot_lines[0] if slot_lines else ""
    type_line = type_lines[0] if type_lines else ""
    type_line = re.sub(r"^\s*Memory Type\s*", "", type_line, flags=re.I).strip()

    if max_lines and all(re.match(r"^\d+GB", line) for line in max_lines):
        out = []
        for line in max_lines:
            capacity = re.match(r"^(\d+GB)", line)
            if not capacity:
                continue
            rendered = capacity.group(1)
            if type_line:
                rendered += f" {type_line}"
            if "soldered" in slot_line.lower() or "soldered" in line.lower():
                rendered += ", soldered"
            out.append(re.sub(r"\s+", " ", rendered).strip(" ,"))
        return base.unique_preserve(out)

    if max_lines:
        first = max_lines[0]
        lowered = slot_line.lower()
        if "two" in lowered and "sodimm" in lowered:
            first = f"{first}, 2x SODIMM"
        elif "one" in lowered and ("so-dimm" in lowered or "sodimm" in lowered):
            first = f"{first}, 1x SO-DIMM"
        elif "soldered" in lowered and "no slots" in lowered and "soldered" not in first.lower():
            first = f"{first}, soldered"
        return [re.sub(r"\s+", " ", first).strip()]
    return []


def extract_graphics_smb(perf: list[str]) -> list[str]:
    lines = base.slice_after_exact_label(perf, ["Graphics", "Graphics**"], ["Monitor Support", "Chipset", "Max Memory", "Memory Slots"])
    keep: list[str] = []
    blob = " ".join(lines).lower()
    xe_eligible = "intel iris xe graphics capability requires" in blob
    pending_integrated = False
    for line in lines:
        lowered = line.lower()
        if base.is_noise_line(line):
            continue
        token = base.normalize_label_token(line)
        if token in {"graphics", "type", "memory", "key features"}:
            continue
        if "directx" in lowered or "shared" in lowered or "tgp" in lowered:
            continue
        if lowered == "integrated":
            pending_integrated = True
            continue
        if "intel iris xe graphics" in lowered:
            rendered = "Intel Iris Xe Graphics eligible (integrated)" if xe_eligible else "Intel Iris Xe Graphics (integrated)"
            keep.append(rendered)
            pending_integrated = False
            continue
        if "intel uhd graphics" in lowered:
            keep.append("Intel UHD Graphics (integrated)")
            pending_integrated = False
            continue
        if any(token in lowered for token in ["nvidia geforce", "amd radeon", "intel arc", "qualcomm adreno"]):
            rendered = re.sub(r"\s+Laptop GPU\b", "", line, flags=re.I).strip()
            rendered = re.sub(r"\s+Laptop\b", "", rendered, flags=re.I).strip()
            if pending_integrated and "(integrated)" not in rendered.lower():
                rendered += " (integrated)"
            keep.append(rendered)
            pending_integrated = False
            continue
    return base.unique_preserve(keep[:4])


def apply_smb_overrides() -> None:
    base.BATTERY_LIFE_PRIORITY = (
        "mobilemark 25",
        "mobilemark",
        "local video",
        "video playback",
        "jeita",
    )
    base.normalize_processor_family_phrase = normalize_processor_family_phrase_smb
    base.extract_processor = extract_processor_smb
    base.extract_graphics = extract_graphics_smb
    base.summarize_memory = summarize_memory_smb
    base.summarize_wlan = summarize_wlan_smb
    base.summarize_ports = summarize_ports_smb
    base.summarize_security = summarize_security_smb
    base.summarize_screen_to_body = summarize_screen_to_body_smb
    base.summarize_case_material = summarize_case_material_smb
    base.summarize_power_adapter = summarize_power_adapter_smb


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Lenovo SMB short specs without an AI model and save them to one Excel workbook."
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
        "--output-mode",
        choices=["auto", "psref_wrapped", "content_only"],
        default="auto",
        help="ShortDesc output wrapper mode.",
    )
    parser.add_argument(
        "--heading-style",
        choices=["modern", "legacy"],
        default="modern",
        help="Section heading style. modern=uppercase, legacy=title case with product name header.",
    )
    parser.add_argument(
        "--runtime-text-dir",
        default="analysis_output/runtime_spec_text_rule_based_smb",
        help="Directory used to cache extracted spec text files.",
    )
    parser.add_argument(
        "--generated-text-dir",
        default="analysis_output/generated_shortspec_batch_rule_based_smb",
        help="Directory used to save generated per-product text outputs.",
    )
    return parser.parse_args()


def main() -> None:
    apply_smb_overrides()
    args = parse_args()
    spec_paths = base.collect_spec_paths(args.spec_pdfs, args.spec_dir, args.glob)
    runtime_text_dir = Path(args.runtime_text_dir).resolve()
    runtime_manifest = runtime_text_dir.parent / "runtime_spec_text_rule_based_smb_manifest.json"
    generated_text_dir = Path(args.generated_text_dir).resolve()
    workbook_path = Path(args.output_xlsx).resolve()

    products = base.load_product_specs(spec_paths, runtime_text_dir, runtime_manifest)

    results: list[base.GenerationResult] = []
    sheets: list[tuple[str, str]] = []
    for product in products:
        print(f"PROCESSING\t{product.product}\t{product.source_path}")
        try:
            shortdesc_text = base.build_shortdesc(
                product_name=product.product,
                spec_text=product.spec_text,
                output_mode=args.output_mode,
                heading_style=args.heading_style,
            )
            result = base.GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="rule_based_smb",
                shortdesc_text=shortdesc_text,
                usage=None,
                response_id=None,
            )
        except Exception as exc:
            result = base.GenerationResult(
                product=product.product,
                source_path=str(product.source_path),
                mode="error",
                shortdesc_text=f"ERROR\nProduct\n{product.product}\nDetails\n{exc}",
                usage=None,
                response_id=None,
                error=str(exc),
            )

        results.append(result)
        sheets.append((product.display_name, result.shortdesc_text))

    base.save_generation_texts(results, generated_text_dir)
    base.write_xlsx(workbook_path, sheets, workbook_layout=args.workbook_layout)
    base.write_manifest(results, workbook_path, args.output_mode, args.heading_style, args.workbook_layout)

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
