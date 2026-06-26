from __future__ import annotations

from storage_shortspec_common import StorageToolConfig, run


CONFIG = StorageToolConfig(
    product_line="thinkstation",
    generator_name="storage_rule_based_thinkstation",
    runtime_text_dir="analysis_output/runtime_spec_text_storage_rule_based_thinkstation",
    generated_text_dir="analysis_output/generated_storage_shortspec_rule_based_thinkstation",
    output_xlsx="storage_shortspecs_rule_based_thinkstation_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
