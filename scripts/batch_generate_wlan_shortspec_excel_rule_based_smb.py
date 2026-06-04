from __future__ import annotations

from wlan_shortspec_common import WLANToolConfig, run


CONFIG = WLANToolConfig(
    product_line="smb",
    generator_name="wlan_rule_based_smb",
    runtime_text_dir="analysis_output/runtime_spec_text_wlan_rule_based_smb",
    generated_text_dir="analysis_output/generated_wlan_shortspec_rule_based_smb",
    output_xlsx="wlan_shortspecs_rule_based_smb_summary.xlsx",
)


if __name__ == "__main__":
    run(CONFIG)
