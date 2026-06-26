from __future__ import annotations

from storage_shortspec_common import StorageToolConfig, run


CONFIG = StorageToolConfig(
    product_line="tablet",
    generator_name="storage_rule_based_tablet",
    runtime_text_dir="analysis_output/runtime_spec_text_storage_rule_based_tablet",
    generated_text_dir="analysis_output/generated_storage_shortspec_rule_based_tablet",
    output_xlsx="storage_shortspecs_rule_based_tablet_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
