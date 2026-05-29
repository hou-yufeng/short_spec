from __future__ import annotations

from display_shortspec_common import DisplayToolConfig, run


CONFIG = DisplayToolConfig(
    product_line="desktop",
    generator_name="display_rule_based_desktop",
    runtime_text_dir="analysis_output/runtime_spec_text_display_rule_based_dt",
    generated_text_dir="analysis_output/generated_display_shortspec_rule_based_dt",
    output_xlsx="display_shortspecs_rule_based_dt_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
