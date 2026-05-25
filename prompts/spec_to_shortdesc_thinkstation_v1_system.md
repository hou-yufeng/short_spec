# ThinkStation System Prompt V1

Source of truth plain-text prompt:
- `D:\learning\shortspec_generator\prompts\spec_to_shortdesc_thinkstation_v1_system.txt`

Aligned rule implementation:
- `D:\learning\shortspec_generator\scripts\batch_generate_shortspec_excel_rule_based_thinkstation.py`

## Positioning

This prompt defines the Lenovo ThinkStation PSREF-to-ShortDesc transformation rules for workstation products.

ThinkStation uses a more independent ShortDesc structure than the generic DT generator. The supported canonical sections are:

- `PERFORMANCE`
- `DESIGN`
- `CONNECTIVITY`
- `SECURITY & PRIVACY`
- `CERTIFICATIONS`

## Canonical Fields

The ThinkStation V1 output uses these fields:

- `PERFORMANCE -> Processor`
- `PERFORMANCE -> Operating System`
- `PERFORMANCE -> Graphics`
- `PERFORMANCE -> Chipset`
- `PERFORMANCE -> Memory`
- `PERFORMANCE -> Storage`
- `PERFORMANCE -> Power Supply`
- `DESIGN -> Dimensions (WxDxH)`
- `DESIGN -> Weight`
- `DESIGN -> Bays`
- `DESIGN -> Expansion Slots`
- `CONNECTIVITY -> Ethernet`
- `CONNECTIVITY -> WLAN + Bluetooth`
- `CONNECTIVITY -> Front Ports`
- `CONNECTIVITY -> Rear Ports`
- `SECURITY & PRIVACY -> Security`
- `SECURITY & PRIVACY -> System Management`
- `CERTIFICATIONS -> ISV Certifications`
- `CERTIFICATIONS -> Green Certifications`
- `CERTIFICATIONS -> Other Certifications`

## Validation Notes

The V1 rule script was validated against `data\training_thinkstation`.

- Spec files processed: `16`
- Products with paired ShortDesc training samples: `15`
- Field-structure coverage for paired samples: no missing expected L1/L2 fields
- Known training-data caveat: `ThinkStation_P4_Spec.PDF` has no paired `ShortDesc_AutoLayout` sample in the current folder.

## Rule Notes

- `System Management` stays under `SECURITY & PRIVACY`, not under the generic DT `MANAGEABILITY` section.
- `ISV Certifications` is a first-class ThinkStation certification field.
- ThinkStation omits generic DT fields such as `Audio`, `Camera`, `Form Factor`, `Color`, `Service`, and `Environmental Material` unless a future training set explicitly changes the canonical output.
- Workstation GPU summaries prioritize `Discrete Graphics Support`, PGX Blackwell architecture details, and compact Tiny discrete offerings.
- PSU wording follows workstation ShortDesc style: fixed supplies are `PSU`; compact adapter systems use `power adapter`.
