from __future__ import annotations

from storage_shortspec_common import StorageToolConfig, run


CONFIG = StorageToolConfig(
    product_line="smb_laptops",
    generator_name="storage_rule_based_smb_laptops",
    runtime_text_dir="analysis_output/runtime_spec_text_storage_rule_based_smb",
    generated_text_dir="analysis_output/generated_storage_shortspec_rule_based_smb",
    output_xlsx="storage_shortspecs_rule_based_smb_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
