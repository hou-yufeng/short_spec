from __future__ import annotations

from wlan_shortspec_common import WLANToolConfig, run


CONFIG = WLANToolConfig(
    product_line="commercial_laptops",
    generator_name="wlan_rule_based_commercial_laptops",
    runtime_text_dir="analysis_output/runtime_spec_text_wlan_rule_based_commercial",
    generated_text_dir="analysis_output/generated_wlan_shortspec_rule_based_commercial",
    output_xlsx="wlan_shortspecs_rule_based_commercial_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
