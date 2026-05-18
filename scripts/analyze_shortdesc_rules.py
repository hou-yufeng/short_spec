from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SHORTDESC_SUFFIX = "_ShortDesc_AutoLayout.pdf"
SPEC_SUFFIX = "_Spec.PDF"
SPEC_SUFFIX_LOWER = "_Spec.pdf"

NOISE_LINES = {
    "PSREF",
    "Product Specifications",
    "Reference",
    "/",
    "•",
}


def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\x07", "")
    text = text.replace("\x0c", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_line(line: str) -> str:
    line = line.replace("\x07", "").replace("\ufeff", "").strip()
    line = re.sub(r"\s+", " ", line)
    return line


def is_probable_section(line: str) -> bool:
    if not line or line in NOISE_LINES:
        return False
    if len(line) > 40:
        return False
    if re.search(r"[a-z]", line):
        return False
    return bool(re.fullmatch(r"[A-Z0-9&/ +\-]+", line))


def is_probable_label(line: str) -> bool:
    if not line or line in NOISE_LINES:
        return False
    if is_probable_section(line):
        return False
    if len(line) > 50:
        return False
    if line.endswith("."):
        return False
    if re.search(r"[,:;]", line):
        return False
    words = line.split()
    if len(words) > 8:
        return False
    if re.search(r"(inch|nits|GHz|GB|TB|Hz|kg|lbs|mm|Wh|MP|%|Windows|Intel|AMD|NVIDIA|Wi-Fi|USB|HDMI)", line, re.I):
        return False
    if not re.search(r"[A-Za-z]", line):
        return False
    return True


def split_lines(text: str) -> list[str]:
    return [normalize_line(line) for line in normalize_text(text).split("\n")]


def read_text(path: Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8"))


@dataclass
class PairRecord:
    product: str
    spec_pdf: str
    short_pdf: str
    spec_txt: Path
    short_txt: Path


def build_pairs(manifest: dict) -> list[PairRecord]:
    by_product: dict[str, dict[str, str]] = defaultdict(dict)
    for item in manifest["extractions"]:
        by_product[item["product"]][item["kind"]] = item["output_txt"]
        by_product[item["product"]][f"{item['kind']}_pdf"] = item["file_name"]

    pairs: list[PairRecord] = []
    for product in sorted(by_product):
        entry = by_product[product]
        if "spec" not in entry or "shortdesc" not in entry:
            raise RuntimeError(f"Incomplete pair for {product}")
        pairs.append(
            PairRecord(
                product=product,
                spec_pdf=entry["spec_pdf"],
                short_pdf=entry["shortdesc_pdf"],
                spec_txt=Path(entry["spec"]),
                short_txt=Path(entry["shortdesc"]),
            )
        )
    return pairs


def parse_shortdesc_structure(text: str) -> dict:
    lines = [line for line in split_lines(text) if line]
    sections: list[dict] = []
    current_section: dict | None = None
    current_label: str | None = None

    for idx, line in enumerate(lines):
        if idx < 3 and line in {"PSREF", "Product Specifications", "Reference"}:
            continue
        if is_probable_section(line):
            current_section = {"name": line, "labels": [], "entries": []}
            sections.append(current_section)
            current_label = None
            continue
        if current_section is None:
            continue

        if is_probable_label(line):
            current_label = line
            if line not in current_section["labels"]:
                current_section["labels"].append(line)
            current_section["entries"].append({"label": line, "values": []})
            continue

        if current_section["entries"]:
            current_section["entries"][-1]["values"].append(line)

    return {
        "section_order": [section["name"] for section in sections],
        "sections": sections,
    }


def line_overlap_ratio(source_lines: Iterable[str], target_lines: Iterable[str]) -> float:
    source = {normalize_line(line).lower() for line in source_lines if normalize_line(line)}
    target = {normalize_line(line).lower() for line in target_lines if normalize_line(line)}
    if not target:
        return 0.0
    matched = sum(1 for line in target if line in source)
    return matched / len(target)


def derive_style_signals(spec_text: str, short_text: str) -> dict:
    spec_lines = [line for line in split_lines(spec_text) if line]
    short_lines = [line for line in split_lines(short_text) if line]

    return {
        "spec_line_count": len(spec_lines),
        "short_line_count": len(short_lines),
        "compression_ratio": round(len(short_text) / max(len(spec_text), 1), 4),
        "line_overlap_ratio": round(line_overlap_ratio(spec_lines, short_lines), 4),
        "spec_has_notes": any("note" in line.lower() for line in spec_lines),
        "short_has_notes": any("note" in line.lower() for line in short_lines),
        "spec_has_legal": any("lenovo reserves the right" in line.lower() for line in spec_lines),
        "short_has_legal": any("lenovo reserves the right" in line.lower() for line in short_lines),
    }


def analyze_pairs(pairs: list[PairRecord]) -> dict:
    section_counter: Counter[str] = Counter()
    section_sequence_counter: Counter[str] = Counter()
    label_counter: Counter[str] = Counter()
    labels_by_section: dict[str, Counter[str]] = defaultdict(Counter)
    product_summaries: list[dict] = []
    example_products_by_section: dict[str, list[str]] = defaultdict(list)

    compression_ratios: list[float] = []
    overlap_ratios: list[float] = []

    for pair in pairs:
        spec_text = read_text(pair.spec_txt)
        short_text = read_text(pair.short_txt)
        structure = parse_shortdesc_structure(short_text)
        style = derive_style_signals(spec_text, short_text)

        compression_ratios.append(style["compression_ratio"])
        overlap_ratios.append(style["line_overlap_ratio"])

        section_names = structure["section_order"]
        section_sequence_counter[" > ".join(section_names)] += 1
        for section in structure["sections"]:
            section_name = section["name"]
            section_counter[section_name] += 1
            if len(example_products_by_section[section_name]) < 8:
                example_products_by_section[section_name].append(pair.product)
            for label in section["labels"]:
                label_counter[label] += 1
                labels_by_section[section_name][label] += 1

        product_summaries.append(
            {
                "product": pair.product,
                "spec_pdf": pair.spec_pdf,
                "short_pdf": pair.short_pdf,
                "section_order": section_names,
                "labels_by_section": {
                    section["name"]: section["labels"] for section in structure["sections"]
                },
                "style_signals": style,
            }
        )

    return {
        "dataset": {
            "pair_count": len(pairs),
            "pdf_count": len(pairs) * 2,
        },
        "section_frequency": dict(section_counter.most_common()),
        "section_sequences": dict(section_sequence_counter.most_common()),
        "label_frequency": dict(label_counter.most_common(200)),
        "labels_by_section": {
            section: dict(counter.most_common()) for section, counter in sorted(labels_by_section.items())
        },
        "example_products_by_section": dict(sorted(example_products_by_section.items())),
        "style_summary": {
            "compression_ratio_min": round(min(compression_ratios), 4) if compression_ratios else 0.0,
            "compression_ratio_max": round(max(compression_ratios), 4) if compression_ratios else 0.0,
            "compression_ratio_avg": round(sum(compression_ratios) / len(compression_ratios), 4) if compression_ratios else 0.0,
            "line_overlap_ratio_min": round(min(overlap_ratios), 4) if overlap_ratios else 0.0,
            "line_overlap_ratio_max": round(max(overlap_ratios), 4) if overlap_ratios else 0.0,
            "line_overlap_ratio_avg": round(sum(overlap_ratios) / len(overlap_ratios), 4) if overlap_ratios else 0.0,
        },
        "products": product_summaries,
    }


def find_possible_conflicts(analysis: dict) -> list[dict]:
    conflicts: list[dict] = []

    seqs = analysis["section_sequences"]
    if len(seqs) > 1:
        sequences = sorted(seqs.items(), key=lambda item: (-item[1], item[0]))
        conflicts.append(
            {
                "type": "section_sequence_variation",
                "message": "Multiple section order patterns detected. Review whether these are allowed variants or contradictory requirements.",
                "details": sequences[:10],
            }
        )

    # Flag labels that appear under more than one section, which may indicate ambiguity.
    label_to_sections: dict[str, set[str]] = defaultdict(set)
    for section, labels in analysis["labels_by_section"].items():
        for label in labels:
            label_to_sections[label].add(section)

    cross_section_labels = {
        label: sorted(sections) for label, sections in label_to_sections.items() if len(sections) > 1
    }
    if cross_section_labels:
        conflicts.append(
            {
                "type": "label_multi_section_usage",
                "message": "Some labels appear in multiple sections. Most are likely acceptable variants, but they need human review before being treated as a hard rule.",
                "details": dict(sorted(cross_section_labels.items())[:50]),
            }
        )

    return conflicts


def render_markdown(analysis: dict, conflicts: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Spec-to-ShortDesc Analysis")
    lines.append("")
    lines.append("## Dataset Coverage")
    lines.append("")
    lines.append(f"- Product pairs analyzed: {analysis['dataset']['pair_count']}")
    lines.append(f"- PDFs analyzed: {analysis['dataset']['pdf_count']}")
    lines.append("")
    lines.append("## Corpus-Level Output Pattern")
    lines.append("")
    for seq, count in analysis["section_sequences"].items():
        lines.append(f"- `{seq}`: {count}")
    lines.append("")
    lines.append("## Section Frequency")
    lines.append("")
    for section, count in analysis["section_frequency"].items():
        lines.append(f"- `{section}`: {count}")
    lines.append("")
    lines.append("## Labels By Section")
    lines.append("")
    for section, labels in analysis["labels_by_section"].items():
        top_labels = ", ".join(f"{label} ({count})" for label, count in list(labels.items())[:20])
        lines.append(f"- `{section}`: {top_labels}")
    lines.append("")
    lines.append("## Style Summary")
    lines.append("")
    style = analysis["style_summary"]
    lines.append(f"- Compression ratio avg/min/max: {style['compression_ratio_avg']} / {style['compression_ratio_min']} / {style['compression_ratio_max']}")
    lines.append(f"- Line overlap ratio avg/min/max: {style['line_overlap_ratio_avg']} / {style['line_overlap_ratio_min']} / {style['line_overlap_ratio_max']}")
    lines.append("")
    lines.append("## Possible Conflicts Requiring Review")
    lines.append("")
    if conflicts:
        for conflict in conflicts:
            lines.append(f"- `{conflict['type']}`: {conflict['message']}")
            lines.append(f"  Details: `{json.dumps(conflict['details'], ensure_ascii=False)[:500]}`")
    else:
        lines.append("- None detected by the current heuristics.")
    lines.append("")
    lines.append("## Product-Level Summaries")
    lines.append("")
    for product in analysis["products"]:
        lines.append(f"- `{product['product']}`")
        lines.append(f"  Section order: `{ ' > '.join(product['section_order']) }`")
        for section, labels in product["labels_by_section"].items():
            lines.append(f"  {section}: `{', '.join(labels)}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="analysis_output/extraction_manifest.json")
    parser.add_argument("--json-out", default="analysis_output/analysis_summary.json")
    parser.add_argument("--md-out", default="analysis_output/analysis_report.md")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
    pairs = build_pairs(manifest)
    analysis = analyze_pairs(pairs)
    conflicts = find_possible_conflicts(analysis)
    analysis["possible_conflicts"] = conflicts

    json_out = Path(args.json_out)
    md_out = Path(args.md_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    md_out.write_text(render_markdown(analysis, conflicts), encoding="utf-8")

    print(f"PAIRS\t{analysis['dataset']['pair_count']}")
    print(f"JSON\t{json_out}")
    print(f"MARKDOWN\t{md_out}")
    print(f"CONFLICTS\t{len(conflicts)}")


if __name__ == "__main__":
    main()
