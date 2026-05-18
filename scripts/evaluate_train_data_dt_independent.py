from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from batch_generate_shortspec_excel import extract_pdf_texts, normalize_text  # noqa: E402
from batch_generate_shortspec_excel_rule_based_dt import DT_L2_LABELS, TOP_LEVEL_SECTIONS  # noqa: E402


DATASET_ROOT = REPO_ROOT / "data" / "train_data_DT"
OUTPUT_DIR = REPO_ROOT / "analysis_output" / "dt_independent_eval"
GENERATED_TEXT_DIR = OUTPUT_DIR / "generated_shortspec_batch_rule_based_dt"
SPEC_TEXT_DIR = OUTPUT_DIR / "runtime_spec_text_rule_based_dt"
ACTUAL_TEXT_DIR = OUTPUT_DIR / "actual_shortdesc_text"
WORKBOOK_PATH = OUTPUT_DIR / "generated_dt_rule_based_summary.xlsx"
REPORT_PATH = OUTPUT_DIR / "train_data_DT_independent_evaluation.md"
DETAILS_PATH = OUTPUT_DIR / "train_data_DT_independent_evaluation_details.json"
PRODUCT_LINES = ("IdeaCentre", "ThinkCentre", "Legion")
REPORT_TOP_FIELDS = 24
REPORT_TOP_PRODUCTS = 30
REPORT_TOP_ACTUAL_ONLY = 30

STOPWORDS = {
    "a",
    "an",
    "and",
    "or",
    "the",
    "with",
    "without",
    "for",
    "to",
    "of",
    "in",
    "on",
    "by",
    "up",
    "at",
    "from",
    "only",
    "selected",
    "models",
    "model",
}

NOISE_PREFIXES = (
    "feature with *",
    "the specifications on this page",
    "lenovo reserves the right",
)

KNOWN_LABELS = sorted(
    set(TOP_LEVEL_SECTIONS)
    | set(DT_L2_LABELS)
    | {
        "Performance",
        "Design",
        "Connectivity",
        "Security & Privacy",
        "Service",
        "Certifications",
        "Green Certifications",
        "Other Certifications",
    },
    key=len,
    reverse=True,
)


@dataclass(frozen=True)
class PairRecord:
    line: str
    product: str
    spec_pdf: Path
    short_pdf: Path


def build_pairs() -> list[PairRecord]:
    pairs: list[PairRecord] = []
    for product_line in PRODUCT_LINES:
        pair_map: dict[str, dict[str, Path]] = defaultdict(dict)
        dataset_dir = DATASET_ROOT / product_line
        for path in sorted(dataset_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() != ".pdf":
                continue
            if path.stem.endswith("_Spec"):
                pair_map[path.stem[: -len("_Spec")]]["spec"] = path.resolve()
            elif path.stem.endswith("_ShortDesc_AutoLayout"):
                pair_map[path.stem[: -len("_ShortDesc_AutoLayout")]]["short"] = path.resolve()
        for product in sorted(pair_map):
            entry = pair_map[product]
            if "spec" not in entry or "short" not in entry:
                raise RuntimeError(f"Incomplete pair: {product_line}/{product}")
            pairs.append(PairRecord(product_line, product, entry["spec"], entry["short"]))
    return pairs


def run_batch_generation() -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "batch_generate_shortspec_excel_rule_based_dt.py"),
        "--spec-dir",
        str(DATASET_ROOT),
        "--glob",
        "**/*_Spec.PDF",
        "--output-xlsx",
        str(WORKBOOK_PATH),
        "--workbook-layout",
        "single_sheet_summary",
        "--runtime-text-dir",
        str(SPEC_TEXT_DIR),
        "--generated-text-dir",
        str(GENERATED_TEXT_DIR),
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def extract_pdf_text(path: Path, out_dir: Path) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{path.name}.txt"
    if target.exists():
        return normalize_text(target.read_text(encoding="utf-8"))
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        text = normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))
        target.write_text(text, encoding="utf-8")
        return text
    except ModuleNotFoundError:
        manifest_path = out_dir.parent / "actual_shortdesc_manifest.json"
        extracted = extract_pdf_texts([path], out_dir, manifest_path)
        return extracted[path.resolve()]


def strip_note_block(text: str) -> str:
    text = normalize_text(text)
    marker = "Note:"
    if marker in text:
        text = text.split(marker, 1)[0]
    return text


def normalize_compare_text(text: str) -> str:
    text = strip_note_block(text)
    text = text.replace("\t", " ").replace("•", " ")
    text = re.sub(r"\[[0-9,\s]+\]", "", text)
    text = text.replace("®", "").replace("™", "").replace("©", "")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def normalize_alnum_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_compare_text(text)).strip()


def tokenize(text: str) -> list[str]:
    return [token for token in normalize_alnum_text(text).split() if token and token not in STOPWORDS]


def split_leading_known_label(line: str) -> list[str]:
    parts: list[str] = []
    remaining = line.strip()
    while remaining:
        matched = False
        for label in KNOWN_LABELS:
            if remaining.lower() == label.lower():
                parts.append(label.upper() if label.upper() in TOP_LEVEL_SECTIONS else label)
                return parts
            if remaining.lower().startswith(label.lower() + " "):
                parts.append(label.upper() if label.upper() in TOP_LEVEL_SECTIONS else label)
                remaining = remaining[len(label) :].strip()
                matched = True
                break
        if not matched:
            parts.append(remaining)
            break
    return parts


def iter_actual_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in strip_note_block(text).replace("\t", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for part in split_leading_known_label(line):
            part = part.strip()
            if part:
                lines.append(part)
    return lines


def is_noise_or_label(line: str) -> bool:
    if not line:
        return True
    if line in {"PSREF", "Product Specifications", "Reference", "/", "Note:"}:
        return True
    if line.upper() in TOP_LEVEL_SECTIONS or line in DT_L2_LABELS or line in KNOWN_LABELS:
        return True
    lowered = line.lower()
    if any(lowered.startswith(prefix) for prefix in NOISE_PREFIXES):
        return True
    if re.search(r"\b\d+ of \d+\b", line):
        return True
    if len(line) <= 1:
        return True
    return False


def extract_actual_fragments(text: str) -> list[str]:
    fragments: list[str] = []
    seen: set[str] = set()
    for line in iter_actual_lines(text):
        if is_noise_or_label(line):
            continue
        if line.isupper() and len(line) <= 50:
            continue
        if len(line) > 180:
            continue
        key = normalize_compare_text(line)
        if not key or key in seen:
            continue
        seen.add(key)
        fragments.append(line)
    return fragments


def best_line_match(item: str, lines: Iterable[str]) -> tuple[float, str]:
    item_norm = normalize_compare_text(item)
    item_tokens = set(tokenize(item))
    best_score = 0.0
    best_line = ""
    for line in lines:
        line_norm = normalize_compare_text(line)
        if not line_norm:
            continue
        seq_score = SequenceMatcher(None, item_norm, line_norm).ratio()
        line_tokens = set(tokenize(line))
        token_score = len(item_tokens & line_tokens) / len(item_tokens) if item_tokens and line_tokens else 0.0
        score = max(seq_score, token_score)
        if score > best_score:
            best_score = score
            best_line = line
    return best_score, best_line


def is_item_matched(item: str, actual_text: str, actual_lines: list[str]) -> tuple[bool, float, str]:
    item_norm = normalize_compare_text(item)
    item_alnum = normalize_alnum_text(item)
    actual_norm = normalize_compare_text(actual_text)
    actual_alnum = normalize_alnum_text(actual_text)
    if item_norm and item_norm in actual_norm:
        return True, 1.0, item
    if item_alnum and item_alnum in actual_alnum:
        return True, 1.0, item
    best_score, best_line = best_line_match(item, actual_lines)
    return (best_score >= 0.93), best_score, best_line


def is_fragment_covered(fragment: str, generated_items: list[str]) -> tuple[bool, float, str]:
    fragment_norm = normalize_compare_text(fragment)
    fragment_alnum = normalize_alnum_text(fragment)
    generated_blob = "\n".join(generated_items)
    generated_norm = normalize_compare_text(generated_blob)
    generated_alnum = normalize_alnum_text(generated_blob)
    if fragment_norm and fragment_norm in generated_norm:
        return True, 1.0, fragment
    if fragment_alnum and fragment_alnum in generated_alnum:
        return True, 1.0, fragment
    best_score, best_item = best_line_match(fragment, generated_items)
    return (best_score >= 0.93), best_score, best_item


def classify_generated_mismatch(item: str, best_line: str, best_score: float) -> str:
    item_tokens = set(tokenize(item))
    line_tokens = set(tokenize(best_line))
    token_overlap = len(item_tokens & line_tokens) / len(item_tokens) if item_tokens else 0.0
    item_numbers = set(re.findall(r"\d+(?:\.\d+)?", item))
    line_numbers = set(re.findall(r"\d+(?:\.\d+)?", best_line))
    if best_score >= 0.75 or token_overlap >= 0.65:
        if item_numbers and line_numbers and item_numbers != line_numbers:
            return "Numeric/value difference"
        return "Wording/layout difference"
    if item_tokens & line_tokens:
        return "Partial content mismatch"
    return "Not found in actual ShortDesc"


def dt_text_to_feature_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    current_l1 = ""
    current_l2 = ""
    for raw_line in text.splitlines():
        line = normalize_text(raw_line).strip()
        if not line:
            continue
        if line in TOP_LEVEL_SECTIONS:
            current_l1 = line
            current_l2 = ""
            continue
        if line in DT_L2_LABELS:
            current_l2 = line
            continue
        if current_l1 and current_l2:
            rows.append((current_l1, current_l2, line))
    return rows


def markdown_escape(text: str) -> str:
    return text.replace("|", "\\|")


def summarize_counter(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def line_summary(rows: list[dict]) -> dict:
    match_rates = [row["generated_item_match_rate"] for row in rows]
    coverage_rates = [row["actual_fragment_coverage_rate"] for row in rows]
    total_generated = sum(row["generated_item_total"] for row in rows)
    total_matched = sum(row["generated_item_matched"] for row in rows)
    total_fragments = sum(row["actual_fragment_total"] for row in rows)
    total_covered = sum(row["actual_fragment_covered"] for row in rows)
    return {
        "products_total": len(rows),
        "generated_item_total": total_generated,
        "generated_item_matched": total_matched,
        "generated_item_match_rate": round(total_matched / total_generated, 4) if total_generated else 0.0,
        "product_match_rate_min": min(match_rates) if match_rates else 0.0,
        "product_match_rate_median": statistics.median(match_rates) if match_rates else 0.0,
        "product_match_rate_avg": round(sum(match_rates) / len(match_rates), 4) if match_rates else 0.0,
        "product_match_rate_max": max(match_rates) if match_rates else 0.0,
        "actual_fragment_total": total_fragments,
        "actual_fragment_covered": total_covered,
        "actual_fragment_coverage_rate": round(total_covered / total_fragments, 4) if total_fragments else 0.0,
        "product_coverage_rate_median": statistics.median(coverage_rates) if coverage_rates else 0.0,
        "product_coverage_rate_avg": round(sum(coverage_rates) / len(coverage_rates), 4) if coverage_rates else 0.0,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs = build_pairs()
    generation = run_batch_generation()

    field_stats: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"total": 0, "matched": 0, "examples": []}
    )
    mismatch_category_counter: Counter[str] = Counter()
    actual_only_counter: Counter[str] = Counter()
    actual_only_examples: dict[str, list[str]] = defaultdict(list)
    product_rows: list[dict] = []

    for pair in pairs:
        generated_path = GENERATED_TEXT_DIR / f"{pair.product}.txt"
        generated_text = normalize_text(generated_path.read_text(encoding="utf-8"))
        actual_text = extract_pdf_text(pair.short_pdf, ACTUAL_TEXT_DIR / pair.line)
        actual_lines = iter_actual_lines(actual_text)
        generated_rows = [
            {"l1": l1, "l2": l2, "item": item}
            for l1, l2, item in dt_text_to_feature_rows(generated_text)
            if item.strip()
        ]
        generated_items = [row["item"] for row in generated_rows]

        unmatched_generated: list[dict] = []
        matched_count = 0
        for row in generated_rows:
            matched, best_score, best_line = is_item_matched(row["item"], actual_text, actual_lines)
            key = (row["l1"], row["l2"])
            field_stats[key]["total"] += 1
            if matched:
                matched_count += 1
                field_stats[key]["matched"] += 1
            else:
                category = classify_generated_mismatch(row["item"], best_line, best_score)
                mismatch_category_counter[category] += 1
                entry = {
                    "l1": row["l1"],
                    "l2": row["l2"],
                    "item": row["item"],
                    "best_actual_line": best_line,
                    "best_score": round(best_score, 4),
                    "category": category,
                }
                unmatched_generated.append(entry)
                examples = field_stats[key]["examples"]
                if len(examples) < 6:
                    examples.append(
                        {
                            "line": pair.line,
                            "product": pair.product,
                            "item": row["item"],
                            "best_actual_line": best_line,
                            "category": category,
                        }
                    )

        actual_fragment_covered = 0
        unmatched_actual_fragments: list[dict] = []
        for fragment in extract_actual_fragments(actual_text):
            if len(tokenize(fragment)) < 2:
                continue
            matched, best_score, best_item = is_fragment_covered(fragment, generated_items)
            if matched:
                actual_fragment_covered += 1
                continue
            unmatched_actual_fragments.append(
                {
                    "fragment": fragment,
                    "best_generated_item": best_item,
                    "best_score": round(best_score, 4),
                }
            )
            actual_only_counter[fragment] += 1
            if len(actual_only_examples[fragment]) < 4:
                actual_only_examples[fragment].append(pair.product)

        actual_fragment_total = actual_fragment_covered + len(unmatched_actual_fragments)
        total_items = len(generated_rows)
        product_rows.append(
            {
                "line": pair.line,
                "product": pair.product,
                "generated_item_total": total_items,
                "generated_item_matched": matched_count,
                "generated_item_match_rate": round(matched_count / total_items, 4) if total_items else 0.0,
                "actual_fragment_total": actual_fragment_total,
                "actual_fragment_covered": actual_fragment_covered,
                "actual_fragment_coverage_rate": round(actual_fragment_covered / actual_fragment_total, 4)
                if actual_fragment_total
                else 0.0,
                "unmatched_generated": unmatched_generated,
                "unmatched_actual_fragments": unmatched_actual_fragments[:12],
            }
        )

    field_rows = []
    for (l1, l2), stat in field_stats.items():
        total = int(stat["total"])
        matched = int(stat["matched"])
        field_rows.append(
            {
                "l1": l1,
                "l2": l2,
                "total": total,
                "matched": matched,
                "unmatched": total - matched,
                "match_rate": round(matched / total, 4) if total else 0.0,
                "examples": stat["examples"],
            }
        )
    field_rows.sort(key=lambda row: (row["match_rate"], -row["unmatched"], row["l1"], row["l2"]))

    line_rows = {
        line: [row for row in product_rows if row["line"] == line]
        for line in PRODUCT_LINES
    }
    line_summaries = {line: line_summary(rows) for line, rows in line_rows.items()}
    overall_summary = line_summary(product_rows)

    details = {
        "dataset": {"pair_count": len(pairs), "pdf_count": len(pairs) * 2},
        "generation_returncode": generation.returncode,
        "generation_stdout": generation.stdout,
        "generation_stderr": generation.stderr,
        "summary": overall_summary,
        "line_summaries": line_summaries,
        "mismatch_categories": dict(summarize_counter(mismatch_category_counter, 20)),
        "fields": field_rows,
        "actual_only_top": [
            {
                "fragment": fragment,
                "count": count,
                "example_products": actual_only_examples[fragment],
            }
            for fragment, count in summarize_counter(actual_only_counter, REPORT_TOP_ACTUAL_ONLY)
        ],
        "worst_products": sorted(
            product_rows,
            key=lambda row: (
                row["generated_item_match_rate"],
                row["actual_fragment_coverage_rate"],
                row["line"],
                row["product"],
            ),
        )[:REPORT_TOP_PRODUCTS],
        "products": product_rows,
    }
    DETAILS_PATH.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# train_data_DT DT 总规则 V1 评估报告")
    lines.append("")
    lines.append("## 评估范围")
    lines.append("")
    lines.append(f"- 数据集目录：`{DATASET_ROOT}`")
    lines.append(f"- 成对产品数：`{len(pairs)}`")
    lines.append(f"- PDF 数：`{len(pairs) * 2}`")
    lines.append("- 生成规则：`scripts/batch_generate_shortspec_excel_rule_based_dt.py`，内部包含 DT common + IdeaCentre / ThinkCentre / Legion profile。")
    lines.append("- 评估口径：生成条目能否在真实 ShortDesc 中定位到，并补充真实 ShortDesc 片段覆盖率。")
    lines.append("")
    lines.append("## 总体结果")
    lines.append("")
    s = overall_summary
    lines.append(f"- 生成条目总数：`{s['generated_item_total']}`")
    lines.append(f"- 生成条目命中率：`{s['generated_item_match_rate']:.4f}`")
    lines.append(f"- 单产品命中率中位数：`{s['product_match_rate_median']:.4f}`")
    lines.append(f"- 真实 ShortDesc 片段覆盖率：`{s['actual_fragment_coverage_rate']:.4f}`")
    lines.append("")
    lines.append("| 产品线 | 产品对 | 生成条目数 | 条目命中率 | 真实片段覆盖率 | 单产品命中率中位数 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for line in PRODUCT_LINES:
        ls = line_summaries[line]
        lines.append(
            f"| {line} | {ls['products_total']} | {ls['generated_item_total']} | {ls['generated_item_match_rate']:.4f} | "
            f"{ls['actual_fragment_coverage_rate']:.4f} | {ls['product_match_rate_median']:.4f} |"
        )
    lines.append("")
    lines.append("## 主要不一致模式")
    lines.append("")
    lines.append("| 类型 | 次数 |")
    lines.append("| --- | ---: |")
    for category, count in details["mismatch_categories"].items():
        lines.append(f"| {markdown_escape(category)} | {count} |")
    lines.append("")
    lines.append("## 低一致性字段")
    lines.append("")
    lines.append("| L1 | L2 | 生成条目数 | 匹配数 | 未匹配数 | 匹配率 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for row in field_rows[:REPORT_TOP_FIELDS]:
        lines.append(
            f"| {markdown_escape(row['l1'])} | {markdown_escape(row['l2'])} | {row['total']} | {row['matched']} | {row['unmatched']} | {row['match_rate']:.4f} |"
        )
    lines.append("")
    lines.append("## 实际 ShortDesc 高频未覆盖片段")
    lines.append("")
    lines.append("| 片段 | 出现次数 | 示例产品 |")
    lines.append("| --- | ---: | --- |")
    for entry in details["actual_only_top"]:
        samples = ", ".join(f"`{product}`" for product in entry["example_products"][:3])
        lines.append(f"| {markdown_escape(entry['fragment'])} | {entry['count']} | {samples} |")
    lines.append("")
    lines.append("## 匹配率最低的产品")
    lines.append("")
    lines.append("| 产品线 | Product | 生成条目数 | 匹配数 | 匹配率 | 覆盖率 | 未匹配示例 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for row in details["worst_products"]:
        examples = "; ".join(markdown_escape(item["item"]) for item in row["unmatched_generated"][:2])
        lines.append(
            f"| {row['line']} | `{row['product']}` | {row['generated_item_total']} | {row['generated_item_matched']} | "
            f"{row['generated_item_match_rate']:.4f} | {row['actual_fragment_coverage_rate']:.4f} | {examples} |"
        )
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"REPORT\t{REPORT_PATH}")
    print(f"DETAILS\t{DETAILS_PATH}")


if __name__ == "__main__":
    main()
