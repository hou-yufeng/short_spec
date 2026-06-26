from __future__ import annotations

from storage_shortspec_common import StorageToolConfig, run


CONFIG = StorageToolConfig(
    product_line="commercial_laptops",
    generator_name="storage_rule_based_commercial_laptops",
    runtime_text_dir="analysis_output/runtime_spec_text_storage_rule_based_commercial",
    generated_text_dir="analysis_output/generated_storage_shortspec_rule_based_commercial",
    output_xlsx="storage_shortspecs_rule_based_commercial_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
