from __future__ import annotations

from display_shortspec_common import DisplayToolConfig, run


CONFIG = DisplayToolConfig(
    product_line="consumer_laptops",
    generator_name="display_rule_based_consumer_laptops",
    runtime_text_dir="analysis_output/runtime_spec_text_display_rule_based_consumer",
    generated_text_dir="analysis_output/generated_display_shortspec_rule_based_consumer",
    output_xlsx="display_shortspecs_rule_based_consumer_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
