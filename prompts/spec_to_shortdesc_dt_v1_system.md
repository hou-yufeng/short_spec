# DT System Prompt V1

Source of truth plain-text prompt:
- `D:\learning\shortspec_generator\prompts\spec_to_shortdesc_dt_v1_system.txt`

Aligned rule implementation:
- `D:\learning\shortspec_generator\scripts\batch_generate_shortspec_excel_rule_based_dt.py`

## Positioning

This prompt defines a Lenovo DT PSREF-to-ShortDesc transformation rule set with one common DT layer and three product-line profiles:

- IdeaCentre
- ThinkCentre
- Legion

It is intended for Excel/database import output where each product is transformed into stable `L1 Feature / L2 Feature / Short Spec` rows.

## Current Coverage

The current DT V1 prompt and rule implementation cover these canonical sections:

- `PERFORMANCE`
- `DESIGN`
- `CONNECTIVITY`
- `SECURITY & PRIVACY`
- `MANAGEABILITY`
- `SERVICE`
- `ENVIRONMENTAL`
- `CERTIFICATIONS`

The latest DT field additions are:

- `PERFORMANCE -> AI PC Category`
- `PERFORMANCE -> NPU`
- `ENVIRONMENTAL -> Material`

Default DT output no longer emits `Stand` or `Mounting` as standalone fields because the training ShortDesc set normally omits them as L2 labels.

## Current Validation

Validation report:
- `D:\learning\shortspec_generator\analysis_output\dt_independent_eval\train_data_DT_independent_evaluation.md`

Validation details:
- `D:\learning\shortspec_generator\analysis_output\dt_independent_eval\train_data_DT_independent_evaluation_details.json`

Current V1 result on `data\train_data_DT` after the DT field-matching pass:

- Product pairs: `169`
- Generated item total: `8640`
- Generated item matched: `6752`
- Generated item match rate: `0.7815`
- Product match-rate median: `0.8108`
- Actual ShortDesc fragment coverage rate: `0.7731`

Line-level result:

| Product Line | Product Pairs | Generated Item Match Rate | Actual Fragment Coverage |
| --- | ---: | ---: | ---: |
| IdeaCentre | 62 | 0.8812 | 0.7590 |
| ThinkCentre | 99 | 0.7375 | 0.7740 |
| Legion | 8 | 0.8281 | 0.8363 |

Known validation caveat:
- `ThinkCentre_M80s_ShortDesc_AutoLayout.pdf.txt` in the cached actual text contains only `ThinkCentre M80s`, so that product scores `0.0000` until the actual ShortDesc text is re-extracted on a machine with working PDF extraction.

## Rule Notes

The prompt is aligned with the current DT rule script behavior:

- AI PC and NPU are emitted under `PERFORMANCE`.
- Material/sustainability claims are emitted under `ENVIRONMENTAL -> Material`.
- Base warranty selects the highest-year customer-facing service and prefers onsite over depot for the same year.
- Optical values are compressed to ShortDesc-style DVD wording.
- 802.11ac WLAN entries are compacted to `802.11ac, Bluetooth X`; newer Wi-Fi 6/6E/7 rows keep marketed detail when useful.
- Green certifications are split into individual values and optional certification markers become trailing `*`.
- MIL-STD long prose is compressed under `Other Certifications`.
- Adapter/PSU wording follows DT ShortDesc conventions for AIO, Tiny, compact, tower, and Legion products.
