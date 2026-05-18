from __future__ import annotations

import json
import sys
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from batch_generate_shortspec_excel import (  # noqa: E402
    normalize_text,
    shortdesc_text_to_feature_rows,
    write_xlsx,
)
from batch_generate_shortspec_excel_rule_based import build_shortdesc  # noqa: E402
from evaluate_training_data_consumer import (  # noqa: E402
    classify_generated_mismatch,
    extract_actual_fragments,
    is_fragment_covered,
    is_item_matched,
    iter_actual_lines,
    markdown_escape,
    normalize_compare_text,
    summarize_counter,
    tokenize,
)


DATASET_ROOT = REPO_ROOT / "data" / "train_data_DT"
PRODUCT_LINES = ("IdeaCentre", "ThinkCentre", "Legion")
OUTPUT_DIR = REPO_ROOT / "analysis_output" / "dt_eval_against_thinkpad_rules"
REPORT_PATH = OUTPUT_DIR / "train_data_DT_against_thinkpad_rules.md"
DETAILS_PATH = OUTPUT_DIR / "train_data_DT_against_thinkpad_rules_details.json"
REPORT_TOP_FIELDS = 18
REPORT_TOP_PRODUCTS = 20
REPORT_TOP_ACTUAL_ONLY = 20


@dataclass(frozen=True)
class PairRecord:
    line: str
    product: str
    spec_pdf: Path
    short_pdf: Path


def build_pairs(product_line: str) -> list[PairRecord]:
    dataset_dir = DATASET_ROOT / product_line
    pair_map: dict[str, dict[str, Path]] = defaultdict(dict)
    for path in sorted(dataset_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        if path.stem.endswith("_Spec"):
            pair_map[path.stem[: -len("_Spec")]]["spec"] = path.resolve()
        elif path.stem.endswith("_ShortDesc_AutoLayout"):
            pair_map[path.stem[: -len("_ShortDesc_AutoLayout")]]["short"] = path.resolve()

    pairs: list[PairRecord] = []
    missing: list[str] = []
    for product in sorted(pair_map):
        entry = pair_map[product]
        if "spec" not in entry or "short" not in entry:
            missing.append(product)
            continue
        pairs.append(
            PairRecord(
                line=product_line,
                product=product,
                spec_pdf=entry["spec"],
                short_pdf=entry["short"],
            )
        )

    if missing:
        raise RuntimeError(f"Incomplete pairs under {dataset_dir}: {missing[:10]}")
    return pairs


def safe_text_name(path: Path) -> str:
    return f"{path.name}.txt"


def extract_pdf_text_with_pypdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return normalize_text("\n".join(parts))


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def evaluate_product_line(product_line: str) -> dict:
    dataset_dir = DATASET_ROOT / product_line
    line_out = OUTPUT_DIR / product_line
    line_out.mkdir(parents=True, exist_ok=True)

    pairs = build_pairs(product_line)
    spec_text_dir = line_out / "runtime_spec_text_rule_based_pypdf"
    actual_text_dir = line_out / "actual_shortdesc_text_pypdf"
    generated_text_dir = line_out / "generated_shortspec_batch_rule_based"
    workbook_path = line_out / f"{product_line}_thinkpad_rule_generated_summary.xlsx"

    product_rows: list[dict] = []
    workbook_sheets: list[tuple[str, str]] = []
    generation_results: list[dict] = []
    generation_failures: list[dict] = []
    field_stats: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"total": 0, "matched": 0, "examples": []}
    )
    mismatch_category_counter: Counter[str] = Counter()
    actual_only_counter: Counter[str] = Counter()
    actual_only_examples: dict[str, list[str]] = defaultdict(list)
    exact_body_match_count = 0

    for pair in pairs:
        error = None
        try:
            spec_text = extract_pdf_text_with_pypdf(pair.spec_pdf)
            save_text(spec_text_dir / safe_text_name(pair.spec_pdf), spec_text)
            generated_text = build_shortdesc(
                product_name=pair.product,
                spec_text=spec_text,
                output_mode="auto",
                heading_style="modern",
            )
        except Exception as exc:
            error = str(exc)
            generated_text = f"ERROR\nProduct\n{pair.product}\nDetails\n{error}"
            generation_failures.append(
                {"product": pair.product, "source_path": str(pair.spec_pdf), "error": error}
            )

        save_text(generated_text_dir / f"{pair.product}{'_error' if error else ''}.txt", generated_text)
        workbook_sheets.append((pair.product, generated_text))
        generation_results.append(
            {
                "product": pair.product,
                "source_path": str(pair.spec_pdf),
                "mode": "rule_based_thinkpad_pypdf",
                "error": error,
            }
        )

        actual_text = extract_pdf_text_with_pypdf(pair.short_pdf)
        save_text(actual_text_dir / safe_text_name(pair.short_pdf), actual_text)
        actual_lines = iter_actual_lines(actual_text)
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
        actual_fragment_covered = 0
        unmatched_actual_fragments: list[dict] = []
        for fragment in actual_fragments:
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
                "line": product_line,
                "product": pair.product,
                "status": "error" if error else "ok",
                "generated_item_total": total_items,
                "generated_item_matched": matched_count,
                "generated_item_match_rate": round(matched_count / total_items, 4) if total_items else 0.0,
                "actual_fragment_total": actual_fragment_total,
                "actual_fragment_covered": actual_fragment_covered,
                "actual_fragment_coverage_rate": round(actual_fragment_covered / actual_fragment_total, 4)
                if actual_fragment_total
                else 0.0,
                "exact_body_match": exact_body_match,
                "unmatched_generated": unmatched_generated,
                "unmatched_actual_fragments": unmatched_actual_fragments[:12],
            }
        )

    write_xlsx(workbook_path, workbook_sheets, workbook_layout="single_sheet_summary")
    manifest_path = workbook_path.with_suffix(".json")
    manifest_path.write_text(
        json.dumps(
            {
                "workbook": str(workbook_path),
                "generator": "rule_based_thinkpad_pypdf",
                "workbook_layout": "single_sheet_summary",
                "results": generation_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
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

    match_rates = [row["generated_item_match_rate"] for row in product_rows]
    coverage_rates = [row["actual_fragment_coverage_rate"] for row in product_rows]
    total_generated_items = sum(row["generated_item_total"] for row in product_rows)
    total_matched_items = sum(row["generated_item_matched"] for row in product_rows)
    total_actual_fragments = sum(row["actual_fragment_total"] for row in product_rows)
    total_covered_fragments = sum(row["actual_fragment_covered"] for row in product_rows)

    return {
        "line": product_line,
        "dataset_dir": str(dataset_dir),
        "pair_count": len(pairs),
        "pdf_count": len(pairs) * 2,
        "generation_command": "pypdf extraction + batch_generate_shortspec_excel_rule_based.build_shortdesc",
        "generation_returncode": 1 if generation_failures else 0,
        "generation_stdout": "",
        "generation_stderr": "",
        "generation_failures": generation_failures,
        "summary": {
            "products_total": len(pairs),
            "products_generated_ok": len(product_rows) - len(generation_failures),
            "products_generation_failed": len(generation_failures),
            "exact_body_match_count": exact_body_match_count,
            "generated_item_total": total_generated_items,
            "generated_item_matched": total_matched_items,
            "generated_item_unmatched": total_generated_items - total_matched_items,
            "generated_item_match_rate": round(total_matched_items / total_generated_items, 4)
            if total_generated_items
            else 0.0,
            "product_match_rate_min": min(match_rates) if match_rates else 0.0,
            "product_match_rate_median": statistics.median(match_rates) if match_rates else 0.0,
            "product_match_rate_avg": round(sum(match_rates) / len(match_rates), 4) if match_rates else 0.0,
            "product_match_rate_max": max(match_rates) if match_rates else 0.0,
            "actual_fragment_total": total_actual_fragments,
            "actual_fragment_covered": total_covered_fragments,
            "actual_fragment_coverage_rate": round(total_covered_fragments / total_actual_fragments, 4)
            if total_actual_fragments
            else 0.0,
            "product_coverage_rate_median": statistics.median(coverage_rates) if coverage_rates else 0.0,
            "product_coverage_rate_avg": round(sum(coverage_rates) / len(coverage_rates), 4)
            if coverage_rates
            else 0.0,
        },
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
                row["product"],
            ),
        )[:REPORT_TOP_PRODUCTS],
        "products": product_rows,
    }


def aggregate_all(line_reports: list[dict]) -> dict:
    products = [row for report in line_reports for row in report["products"]]
    field_acc: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"total": 0, "matched": 0, "examples": []}
    )
    mismatch_counter: Counter[str] = Counter()
    actual_only_counter: Counter[str] = Counter()
    actual_only_examples: dict[str, list[str]] = defaultdict(list)

    for report in line_reports:
        mismatch_counter.update(report["mismatch_categories"])
        for field in report["fields"]:
            key = (field["l1"], field["l2"])
            field_acc[key]["total"] += field["total"]
            field_acc[key]["matched"] += field["matched"]
            examples = field_acc[key]["examples"]
            for example in field["examples"]:
                if len(examples) < 6:
                    examples.append(example)
        for entry in report["actual_only_top"]:
            actual_only_counter[entry["fragment"]] += entry["count"]
            examples = actual_only_examples[entry["fragment"]]
            for product in entry["example_products"]:
                if len(examples) < 4:
                    examples.append(product)

    field_rows = []
    for (l1, l2), stat in field_acc.items():
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

    match_rates = [row["generated_item_match_rate"] for row in products]
    coverage_rates = [row["actual_fragment_coverage_rate"] for row in products]
    total_generated_items = sum(row["generated_item_total"] for row in products)
    total_matched_items = sum(row["generated_item_matched"] for row in products)
    total_actual_fragments = sum(row["actual_fragment_total"] for row in products)
    total_covered_fragments = sum(row["actual_fragment_covered"] for row in products)

    return {
        "summary": {
            "products_total": len(products),
            "pdf_count": len(products) * 2,
            "generated_item_total": total_generated_items,
            "generated_item_matched": total_matched_items,
            "generated_item_match_rate": round(total_matched_items / total_generated_items, 4)
            if total_generated_items
            else 0.0,
            "product_match_rate_min": min(match_rates) if match_rates else 0.0,
            "product_match_rate_median": statistics.median(match_rates) if match_rates else 0.0,
            "product_match_rate_avg": round(sum(match_rates) / len(match_rates), 4) if match_rates else 0.0,
            "product_match_rate_max": max(match_rates) if match_rates else 0.0,
            "actual_fragment_total": total_actual_fragments,
            "actual_fragment_covered": total_covered_fragments,
            "actual_fragment_coverage_rate": round(total_covered_fragments / total_actual_fragments, 4)
            if total_actual_fragments
            else 0.0,
            "product_coverage_rate_median": statistics.median(coverage_rates) if coverage_rates else 0.0,
            "product_coverage_rate_avg": round(sum(coverage_rates) / len(coverage_rates), 4)
            if coverage_rates
            else 0.0,
        },
        "fields": field_rows,
        "mismatch_categories": dict(summarize_counter(mismatch_counter, 20)),
        "actual_only_top": [
            {
                "fragment": fragment,
                "count": count,
                "example_products": actual_only_examples[fragment],
            }
            for fragment, count in summarize_counter(actual_only_counter, REPORT_TOP_ACTUAL_ONLY)
        ],
        "worst_products": sorted(
            products,
            key=lambda row: (
                row["generated_item_match_rate"],
                row["actual_fragment_coverage_rate"],
                row["line"],
                row["product"],
            ),
        )[:REPORT_TOP_PRODUCTS],
    }


def applicability_label(match_rate: float, coverage_rate: float) -> str:
    if match_rate >= 0.80 and coverage_rate >= 0.55:
        return "较高"
    if match_rate >= 0.65 and coverage_rate >= 0.40:
        return "中等"
    return "较低"


def render_report(line_reports: list[dict], overall: dict) -> str:
    lines: list[str] = []
    lines.append("# ThinkPad 转换规则在 DT 产品线上的适用性评估")
    lines.append("")
    lines.append("## 评估结论")
    lines.append("")
    summary = overall["summary"]
    overall_label = applicability_label(
        summary["generated_item_match_rate"],
        summary["actual_fragment_coverage_rate"],
    )
    lines.append(
        f"- 总体适用程度：**{overall_label}**。ThinkPad 规则在 DT 数据集上生成条目的命中率为 "
        f"`{summary['generated_item_match_rate']:.4f}`，但对真实 ShortDesc 片段的覆盖率为 "
        f"`{summary['actual_fragment_coverage_rate']:.4f}`。"
    )
    lines.append(
        "- 这说明 ThinkPad 规则能复用一部分通用字段，例如处理器、操作系统、内存、存储、显卡、端口、认证等；但 DT 产品存在明显的桌面/AIO/游戏台式机专属结构，不能直接把 ThinkPad 规则作为最终规则。"
    )
    lines.append(
        "- 从产品线看，Legion 和 IdeaCentre 的生成条目命中率高于 ThinkCentre，但 Legion 的真实内容覆盖率最低；ThinkCentre 的真实内容覆盖率相对最高，不过 ThinkPad 规则在处理器、尺寸、WLAN、摄像头等字段上仍有大量措辞和字段体系不匹配。"
    )
    lines.append("")

    lines.append("## 评估方法")
    lines.append("")
    lines.append(f"- 数据集根目录：`{DATASET_ROOT}`")
    lines.append("- 使用规则：现有 ThinkPad 规则版生成器 `scripts/batch_generate_shortspec_excel_rule_based.py`。")
    lines.append("- 评估对象：`IdeaCentre`、`ThinkCentre`、`Legion` 三个目录中完整成对的 `*_Spec.PDF` 与 `*_ShortDesc_AutoLayout.pdf`。")
    lines.append("- 评估口径一：生成端 `L1 / L2 / value item` 条目能否在真实 ShortDesc 抽取文本中定位到，作为生成条目命中率。")
    lines.append("- 评估口径二：真实 ShortDesc 中的可见片段能否被生成条目覆盖，作为真实内容覆盖率。这个指标更容易受 PDF 双栏抽取影响，但能暴露漏生成方向。")
    lines.append("")

    lines.append("## 总览")
    lines.append("")
    lines.append("| 范围 | 产品对 | PDF 数 | 生成条目数 | 条目命中率 | 真实片段覆盖率 | 单产品命中率中位数 | 适用程度 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    lines.append(
        f"| 全部 DT | {summary['products_total']} | {summary['pdf_count']} | {summary['generated_item_total']} | "
        f"{summary['generated_item_match_rate']:.4f} | {summary['actual_fragment_coverage_rate']:.4f} | "
        f"{summary['product_match_rate_median']:.4f} | {overall_label} |"
    )
    for report in line_reports:
        s = report["summary"]
        label = applicability_label(s["generated_item_match_rate"], s["actual_fragment_coverage_rate"])
        lines.append(
            f"| {report['line']} | {s['products_total']} | {report['pdf_count']} | {s['generated_item_total']} | "
            f"{s['generated_item_match_rate']:.4f} | {s['actual_fragment_coverage_rate']:.4f} | "
            f"{s['product_match_rate_median']:.4f} | {label} |"
        )
    lines.append("")

    lines.append("## 总体不一致模式")
    lines.append("")
    lines.append("| 类型 | 次数 |")
    lines.append("| --- | ---: |")
    for category, count in overall["mismatch_categories"].items():
        lines.append(f"| {markdown_escape(category)} | {count} |")
    lines.append("")

    lines.append("## 总体低一致性字段")
    lines.append("")
    lines.append("| L1 | L2 | 生成条目数 | 匹配数 | 未匹配数 | 匹配率 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for row in overall["fields"][:REPORT_TOP_FIELDS]:
        lines.append(
            f"| {markdown_escape(row['l1'])} | {markdown_escape(row['l2'])} | {row['total']} | "
            f"{row['matched']} | {row['unmatched']} | {row['match_rate']:.4f} |"
        )
    lines.append("")

    lines.append("## 分产品线分析")
    lines.append("")
    for report in line_reports:
        s = report["summary"]
        label = applicability_label(s["generated_item_match_rate"], s["actual_fragment_coverage_rate"])
        lines.append(f"### {report['line']}")
        lines.append("")
        lines.append(f"- 适用程度：**{label}**")
        lines.append(f"- 产品对：`{s['products_total']}`，PDF：`{report['pdf_count']}`")
        lines.append(
            f"- 生成条目命中率：`{s['generated_item_match_rate']:.4f}`；单产品命中率中位数：`{s['product_match_rate_median']:.4f}`"
        )
        lines.append(
            f"- 真实片段覆盖率：`{s['actual_fragment_coverage_rate']:.4f}`；单产品覆盖率中位数：`{s['product_coverage_rate_median']:.4f}`"
        )
        if report["generation_failures"]:
            lines.append(f"- 生成失败：`{len(report['generation_failures'])}`")
        lines.append("")
        lines.append("| 低一致性字段 | 生成条目数 | 未匹配数 | 匹配率 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for row in report["fields"][:8]:
            lines.append(
                f"| {markdown_escape(row['l1'] + ' -> ' + row['l2'])} | {row['total']} | {row['unmatched']} | {row['match_rate']:.4f} |"
            )
        lines.append("")
        lines.append("| 真实 ShortDesc 高频未覆盖片段 | 出现次数 | 示例产品 |")
        lines.append("| --- | ---: | --- |")
        for entry in report["actual_only_top"][:8]:
            sample = ", ".join(f"`{product}`" for product in entry["example_products"][:3])
            lines.append(f"| {markdown_escape(entry['fragment'])} | {entry['count']} | {sample} |")
        lines.append("")

    lines.append("## 匹配率最低的产品")
    lines.append("")
    lines.append("| 产品线 | Product | 生成条目数 | 匹配数 | 条目命中率 | 真实片段覆盖率 | 未匹配条目示例 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for row in overall["worst_products"]:
        examples = "; ".join(markdown_escape(item["item"]) for item in row["unmatched_generated"][:2])
        lines.append(
            f"| {row['line']} | `{row['product']}` | {row['generated_item_total']} | {row['generated_item_matched']} | "
            f"{row['generated_item_match_rate']:.4f} | {row['actual_fragment_coverage_rate']:.4f} | {examples} |"
        )
    lines.append("")

    lines.append("## 规则适用性判断")
    lines.append("")
    lines.append("1. **可复用部分**：ThinkPad 规则中的基础硬件抽取、规范化、Excel 层级输出结构可以保留作为 DT 规则的底座。处理器、操作系统、内存、存储、显卡、端口、认证类字段有一定迁移价值。")
    lines.append("2. **不可直接复用部分**：ThinkPad 规则围绕笔记本建立，天然强调电池、屏幕、键盘、触控板、重量、材料、WWAN/NFC、摄像头隐私等字段；DT 产品的真实 ShortDesc 更关注桌面形态、AIO 屏幕/支架、机箱尺寸、扩展槽、显卡/电源、接口布局、游戏特性和商用管理。")
    lines.append("3. **产品线差异**：ThinkCentre 更接近商用规则体系，适合在 ThinkPad 规则基础上分支扩展；IdeaCentre 和 Legion 需要更强的独立规则，因为消费台式机、AIO 和游戏台式机的表达与字段优先级不同。")
    lines.append("4. **建议下一步**：不要把 ThinkPad 规则直接用于 DT 最终生成。建议新建 `batch_generate_shortspec_excel_rule_based_dt.py`，复用通用抽取/Excel 输出模块，但单独学习 DT 的 L1/L2 标签、字段保留优先级和产品线分支规则。")
    lines.append("")

    lines.append("## 产物")
    lines.append("")
    lines.append(f"- 详情 JSON：`{DETAILS_PATH}`")
    lines.append(f"- 生成结果目录：`{OUTPUT_DIR}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    line_reports = [evaluate_product_line(line) for line in PRODUCT_LINES]
    overall = aggregate_all(line_reports)
    details = {"overall": overall, "lines": line_reports}
    DETAILS_PATH.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(render_report(line_reports, overall), encoding="utf-8")
    print(f"REPORT\t{REPORT_PATH}")
    print(f"DETAILS\t{DETAILS_PATH}")


if __name__ == "__main__":
    main()
