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

from batch_generate_shortspec_excel import (  # noqa: E402
    L2_FEATURES,
    TOP_LEVEL_FEATURES,
    extract_pdf_texts,
    normalize_text,
    shortdesc_text_to_feature_rows,
)


DATASET_DIR = REPO_ROOT / "data" / "train_data_SMB"
OUTPUT_DIR = REPO_ROOT / "analysis_output" / "smb_eval_against_training_rules"
GENERATED_TEXT_DIR = OUTPUT_DIR / "generated_shortspec_batch_rule_based"
SPEC_TEXT_DIR = OUTPUT_DIR / "runtime_spec_text_rule_based"
ACTUAL_TEXT_DIR = OUTPUT_DIR / "actual_shortdesc_text"
ACTUAL_MANIFEST = OUTPUT_DIR / "actual_shortdesc_manifest.json"
WORKBOOK_PATH = OUTPUT_DIR / "generated_smb_rule_based_summary.xlsx"
REPORT_PATH = OUTPUT_DIR / "train_data_SMB_evaluation_against_training_rules.md"
DETAILS_PATH = OUTPUT_DIR / "train_data_SMB_evaluation_against_training_rules_details.json"

SPEC_SUFFIX = "_Spec.PDF"
SHORT_SUFFIX = "_ShortDesc_AutoLayout.pdf"
REPORT_TOP_PRODUCTS = 40
REPORT_TOP_FIELDS = 20
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
NOISE_LINES = {
    "PSREF",
    "Product Specifications",
    "Reference",
    "Note:",
    "/",
    "Notes:",
}
NOISE_PREFIXES = (
    "feature with *",
    "the specifications on this page",
    "lenovo reserves the right",
)

KNOWN_LABELS = sorted(
    set(TOP_LEVEL_FEATURES)
    | set(L2_FEATURES)
    | {
        "Special Features",
        "Case Color",
        "Green Certifications",
        "Other Certifications",
        "Material",
        "Processor",
        "Operating System",
        "Graphics",
        "Memory",
        "Storage",
        "Audio",
        "Camera",
        "Battery",
        "Power Adapter",
        "Display",
        "Keyboard",
        "Touchpad",
        "Dimensions (WxDxH)",
        "Weight",
        "Color",
        "Case Material",
        "WLAN + Bluetooth",
        "Ports",
        "Security",
    },
    key=len,
    reverse=True,
)


@dataclass(frozen=True)
class PairRecord:
    product: str
    spec_pdf: Path
    short_pdf: Path


def build_pairs(dataset_dir: Path) -> list[PairRecord]:
    pair_map: dict[str, dict[str, Path]] = defaultdict(dict)
    for path in sorted(dataset_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(SPEC_SUFFIX):
            pair_map[name[: -len(SPEC_SUFFIX)]]["spec"] = path.resolve()
        elif name.endswith(SHORT_SUFFIX):
            pair_map[name[: -len(SHORT_SUFFIX)]]["short"] = path.resolve()

    pairs: list[PairRecord] = []
    missing: list[str] = []
    for product in sorted(pair_map):
        entry = pair_map[product]
        if "spec" not in entry or "short" not in entry:
            missing.append(product)
            continue
        pairs.append(PairRecord(product=product, spec_pdf=entry["spec"], short_pdf=entry["short"]))

    if missing:
        raise RuntimeError(f"Incomplete pairs in train_data_SMB: {missing[:10]}")
    return pairs


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    ACTUAL_TEXT_DIR.mkdir(parents=True, exist_ok=True)


def run_batch_generation() -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "batch_generate_shortspec_excel_rule_based.py"),
        "--spec-dir",
        str(DATASET_DIR),
        "--glob",
        "*_Spec.PDF",
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


def strip_note_block(text: str) -> str:
    text = normalize_text(text)
    marker = "Note:"
    if marker in text:
        text = text.split(marker, 1)[0]
    return text


def normalize_compare_text(text: str) -> str:
    text = strip_note_block(text)
    text = text.replace("\t", " ")
    text = text.replace("•", " ")
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
            if remaining == label:
                parts.append(label)
                return parts
            if remaining.startswith(label + " "):
                parts.append(label)
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
    if line in NOISE_LINES:
        return True
    if line in TOP_LEVEL_FEATURES or line in L2_FEATURES or line in KNOWN_LABELS:
        return True
    lowered = line.lower()
    if any(lowered.startswith(prefix) for prefix in NOISE_PREFIXES):
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
        if item_tokens and line_tokens:
            token_score = len(item_tokens & line_tokens) / len(item_tokens)
        else:
            token_score = 0.0
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
    if best_score >= 0.93:
        return True, best_score, best_line
    return False, best_score, best_line


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
    if best_score >= 0.93:
        return True, best_score, best_item
    return False, best_score, best_item


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


def markdown_escape(text: str) -> str:
    return text.replace("|", "\\|")


def summarize_counter(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def main() -> None:
    ensure_dirs()
    pairs = build_pairs(DATASET_DIR)

    generation = run_batch_generation()

    actual_text_map = extract_pdf_texts(
        [pair.short_pdf for pair in pairs],
        ACTUAL_TEXT_DIR,
        ACTUAL_MANIFEST,
    )

    product_rows: list[dict] = []
    field_stats: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"total": 0, "matched": 0, "examples": []}
    )
    mismatch_category_counter: Counter[str] = Counter()
    actual_only_counter: Counter[str] = Counter()
    actual_only_examples: dict[str, list[str]] = defaultdict(list)
    exact_body_match_count = 0
    generation_failures: list[dict] = []

    for pair in pairs:
        generated_path = GENERATED_TEXT_DIR / f"{pair.product}.txt"
        error_path = GENERATED_TEXT_DIR / f"{pair.product}_error.txt"
        actual_text = actual_text_map[pair.short_pdf]
        actual_lines = [line for line in iter_actual_lines(actual_text) if not is_noise_or_label(line)]

        if error_path.exists() and not generated_path.exists():
            error_text = error_path.read_text(encoding="utf-8")
            generation_failures.append({"product": pair.product, "error": error_text.strip()})
            product_rows.append(
                {
                    "product": pair.product,
                    "status": "generation_failed",
                    "generated_item_total": 0,
                    "generated_item_matched": 0,
                    "generated_item_match_rate": 0.0,
                    "exact_body_match": False,
                    "unmatched_generated": [],
                    "unmatched_actual_fragments": [],
                }
            )
            continue

        if not generated_path.exists():
            raise FileNotFoundError(f"Generated output missing for {pair.product}: {generated_path}")

        generated_text = generated_path.read_text(encoding="utf-8")
        generated_rows = [
            {"l1": l1, "l2": l2, "item": item}
            for l1, l2, item in shortdesc_text_to_feature_rows(generated_text)
            if item.strip()
        ]
        generated_items = [row["item"] for row in generated_rows]

        exact_body_match = normalize_compare_text(generated_text) == normalize_compare_text(actual_text)
        if exact_body_match:
            exact_body_match_count += 1

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
                            "product": pair.product,
                            "item": row["item"],
                            "best_actual_line": best_line,
                            "category": category,
                        }
                    )

        actual_fragments = extract_actual_fragments(actual_text)
        unmatched_actual_fragments: list[dict] = []
        for fragment in actual_fragments:
            matched, best_score, best_item = is_fragment_covered(fragment, generated_items)
            if matched:
                continue
            if len(tokenize(fragment)) < 2:
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

        total_items = len(generated_rows)
        match_rate = round(matched_count / total_items, 4) if total_items else 0.0
        product_rows.append(
            {
                "product": pair.product,
                "status": "ok",
                "generated_item_total": total_items,
                "generated_item_matched": matched_count,
                "generated_item_match_rate": match_rate,
                "exact_body_match": exact_body_match,
                "unmatched_generated": unmatched_generated,
                "unmatched_actual_fragments": unmatched_actual_fragments[:12],
            }
        )

    ok_rows = [row for row in product_rows if row["status"] == "ok"]
    match_rates = [row["generated_item_match_rate"] for row in ok_rows]
    total_generated_items = sum(row["generated_item_total"] for row in ok_rows)
    total_matched_items = sum(row["generated_item_matched"] for row in ok_rows)
    total_unmatched_items = total_generated_items - total_matched_items

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

    worst_products = sorted(
        ok_rows,
        key=lambda row: (row["generated_item_match_rate"], -len(row["unmatched_generated"]), row["product"]),
    )[:REPORT_TOP_PRODUCTS]

    details = {
        "dataset": {
            "pair_count": len(pairs),
            "pdf_count": len(pairs) * 2,
        },
        "generation_command": generation.args,
        "generation_returncode": generation.returncode,
        "generation_stdout": generation.stdout,
        "generation_stderr": generation.stderr,
        "generation_failures": generation_failures,
        "summary": {
            "products_total": len(pairs),
            "products_generated_ok": len(ok_rows),
            "products_generation_failed": len(generation_failures),
            "exact_body_match_count": exact_body_match_count,
            "generated_item_total": total_generated_items,
            "generated_item_matched": total_matched_items,
            "generated_item_unmatched": total_unmatched_items,
            "generated_item_match_rate": round(total_matched_items / total_generated_items, 4)
            if total_generated_items
            else 0.0,
            "product_match_rate_min": min(match_rates) if match_rates else 0.0,
            "product_match_rate_median": statistics.median(match_rates) if match_rates else 0.0,
            "product_match_rate_avg": round(sum(match_rates) / len(match_rates), 4) if match_rates else 0.0,
            "product_match_rate_max": max(match_rates) if match_rates else 0.0,
        },
        "mismatch_categories": dict(summarize_counter(mismatch_category_counter, 20)),
        "fields": field_rows,
        "worst_products": worst_products,
        "actual_only_top": [
            {
                "fragment": fragment,
                "count": count,
                "example_products": actual_only_examples[fragment],
            }
            for fragment, count in summarize_counter(actual_only_counter, REPORT_TOP_ACTUAL_ONLY)
        ],
        "products": product_rows,
    }
    DETAILS_PATH.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# train_data_SMB 全量评估报告")
    lines.append("")
    lines.append("## 评估范围")
    lines.append("")
    lines.append(f"- 数据集目录：`{DATASET_DIR}`")
    lines.append(f"- 成对产品数：`{len(pairs)}`")
    lines.append(f"- 参与评估的 PDF 数：`{len(pairs) * 2}`")
    lines.append("- 评估方式：对 `train_data_SMB` 下全部 `*_Spec.PDF` 执行现有 `training_data` / ThinkPad 规则版批处理程序，再与对应 `*_ShortDesc_AutoLayout.pdf` 的实际文本进行对比。")
    lines.append("- 评估口径：以生成端的 `L1/L2/value item` 为主，检查每个生成条目是否能在实际 `ShortDesc` 抽取文本中找到；同时补充统计实际 `ShortDesc` 中未被生成覆盖的高频片段。")
    lines.append("- 说明：实际 `ShortDesc` PDF 是双栏排版，抽取文本存在跨栏串行、同一行混入多个字段的问题，因此本报告优先使用“生成条目是否能在实际文本中定位到”的方法来评估一致性，而不是仅比较版式。")
    lines.append("")
    lines.append("## 批处理执行结果")
    lines.append("")
    lines.append(f"- 批处理返回码：`{generation.returncode}`")
    lines.append(f"- 成功生成产品数：`{len(ok_rows)}`")
    lines.append(f"- 生成失败产品数：`{len(generation_failures)}`")
    lines.append(f"- 输出工作簿：`{WORKBOOK_PATH}`")
    lines.append(f"- Markdown 详情 JSON：`{DETAILS_PATH}`")
    lines.append("")
    if generation_failures:
        lines.append("### 生成失败产品")
        lines.append("")
        for failure in generation_failures:
            lines.append(f"- `{failure['product']}`")
        lines.append("")

    summary = details["summary"]
    lines.append("## 总体一致性结果")
    lines.append("")
    lines.append(f"- 规范化全文完全一致产品数：`{summary['exact_body_match_count']}` / `{len(pairs)}`")
    lines.append(
        f"- 生成条目总数：`{summary['generated_item_total']}`，其中能在实际 `ShortDesc` 中定位到的条目数：`{summary['generated_item_matched']}`"
    )
    lines.append(f"- 生成条目匹配率：`{summary['generated_item_match_rate']:.4f}`")
    lines.append(f"- 单产品匹配率最小值：`{summary['product_match_rate_min']:.4f}`")
    lines.append(f"- 单产品匹配率中位数：`{summary['product_match_rate_median']:.4f}`")
    lines.append(f"- 单产品匹配率平均值：`{summary['product_match_rate_avg']:.4f}`")
    lines.append(f"- 单产品匹配率最大值：`{summary['product_match_rate_max']:.4f}`")
    lines.append("")

    lines.append("## 主要不一致模式")
    lines.append("")
    lines.append("### 1. 按不一致类型汇总")
    lines.append("")
    lines.append("| 类型 | 次数 |")
    lines.append("| --- | ---: |")
    for category, count in summarize_counter(mismatch_category_counter, 20):
        lines.append(f"| {markdown_escape(category)} | {count} |")
    lines.append("")

    lines.append("### 2. 按字段汇总的低一致性项")
    lines.append("")
    lines.append("| L1 | L2 | 生成条目数 | 匹配数 | 未匹配数 | 匹配率 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for row in field_rows[:REPORT_TOP_FIELDS]:
        lines.append(
            f"| {markdown_escape(row['l1'])} | {markdown_escape(row['l2'])} | {row['total']} | {row['matched']} | {row['unmatched']} | {row['match_rate']:.4f} |"
        )
    lines.append("")

    for row in field_rows[:10]:
        if not row["examples"]:
            continue
        lines.append(f"#### 示例：`{row['l1']} -> {row['l2']}`")
        lines.append("")
        for example in row["examples"][:3]:
            lines.append(f"- `{example['product']}`")
            lines.append(f"  生成条目：`{example['item']}`")
            if example["best_actual_line"]:
                lines.append(f"  实际最接近文本：`{example['best_actual_line']}`")
            lines.append(f"  判断：`{example['category']}`")
        lines.append("")

    lines.append("### 3. 实际 ShortDesc 中高频但未被生成覆盖的片段")
    lines.append("")
    lines.append("这部分是辅助视角，目的是识别实际 `ShortDesc` 常见而当前生成结果经常没有覆盖的内容。由于 PDF 双栏抽取会把相邻字段串到同一行，这里的统计比“生成条目匹配率”更容易受版式影响。")
    lines.append("")
    lines.append("| 片段 | 出现次数 | 示例产品 |")
    lines.append("| --- | ---: | --- |")
    for entry in details["actual_only_top"]:
        sample_products = ", ".join(f"`{product}`" for product in entry["example_products"][:3])
        lines.append(
            f"| {markdown_escape(entry['fragment'])} | {entry['count']} | {sample_products} |"
        )
    lines.append("")

    lines.append("## 匹配率最低的产品")
    lines.append("")
    lines.append("| Product | 生成条目数 | 匹配数 | 匹配率 | 未匹配条目示例 |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for row in worst_products:
        examples = "; ".join(
            markdown_escape(item["item"]) for item in row["unmatched_generated"][:2]
        )
        lines.append(
            f"| `{row['product']}` | {row['generated_item_total']} | {row['generated_item_matched']} | {row['generated_item_match_rate']:.4f} | {examples} |"
        )
    lines.append("")

    lines.append("## 全量产品覆盖清单")
    lines.append("")
    lines.append("| Product | 状态 | 生成条目数 | 匹配数 | 匹配率 | 规范化全文完全一致 |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for row in sorted(product_rows, key=lambda item: item["product"]):
        lines.append(
            f"| `{row['product']}` | {row['status']} | {row['generated_item_total']} | {row['generated_item_matched']} | {row['generated_item_match_rate']:.4f} | {row['exact_body_match']} |"
        )
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"REPORT\t{REPORT_PATH}")
    print(f"DETAILS\t{DETAILS_PATH}")


if __name__ == "__main__":
    main()
