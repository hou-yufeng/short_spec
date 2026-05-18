# Tablet Spec-to-ShortDesc Rules V1

This document records the rule-based conversion used by `batch_generate_shortspec_excel_rule_based_tablet.py`.

## Output Structure

- Top-level sections: `PERFORMANCE`, `DESIGN`, `CONNECTIVITY`, `SECURITY & PRIVACY`, `ACCESSORIES`, `CERTIFICATIONS`.
- Excel rows are exported as `Product / L1 Feature / L2 Feature / Short Spec` in summary mode.
- Repeated values under one L2 feature are kept as multiple generated text lines and aggregated into newline bullets by the shared Excel writer.
- Optional PSREF bullets are represented with `*` where tablet ShortDesc convention depends on it, especially `WWAN`, energy rating, and MIL-STD items.
- Service, warranty, operating environment, and preinstalled software are not emitted.

## PERFORMANCE

- `Processor`: use `Processor > Processor Name` table. Keep processor name and core topology. Remove max-frequency, memory-support, and processor-graphics columns. Keep `Mobile Platform` names as a phrase.
- `Operating System`: use first value under `Operating System`; remove trademark and footnote markers.
- `Graphics`: use first value under `Graphics`; remove trademark markers.
- `Memory`: use `Max Memory` capacities plus `Memory Type`; render as `{capacity} {type}, soldered` when soldered or not-upgradable.
- `Storage`: use `Max Storage Support`; group internal capacities by storage technology (`eMMC 5.1`, `UFS 2.2`, `UFS 3.1`, `UFS 4.0`, `UFS`) and keep microSD support as a separate line.
- `Audio`: use `Speakers` and `Microphone`; remove `optimized with` wording while preserving branded speaker wording such as JBL or Harman Kardon.
- `Camera`: use `Camera` / `Camera**`; group front and rear cameras into `Front ... + rear ...`, keep autofocus, flashlight, and macro descriptors, and remove long aperture/FoV/video-recording details.
- `Sensors`: use `Sensor`; include vibration motor and sensor list, skip `No support`, duplicate sublabels, and page headers.
- `Battery`: use `Battery` capacity plus selected `Max Battery Life` rows; normalize colon forms such as `Video playback: 10 hr` to `Video playback up to 10 hr`.
- `Charging Time`: emit only when the tablet ShortDesc has a separate charging-time feature.
- `Power Adapter`: use adapter rows under `Power Adapter`; skip `No power adapter`, remove input-voltage ranges, and normalize common USB-C AC adapter wording.

## DESIGN

- `Display`: parse the PSREF display table; emit size, marketed resolution, panel type, surface, aspect ratio, brightness, touch, gamut, refresh rate, and key display certifications/features.
- `Screen-to-Body Ratio`: use the explicit ratio value when present.
- `Pen`: use bundled pen rows; skip `No pen bundled` unless it is the only pen result, in which case emit `No pen (purchase separately)`.
- `Dimensions (WxDxH)`: use mechanical dimensions, including metric and inch values when provided.
- `Weight`: use the mechanical weight line.
- `Color`: use `Case Color`, preserving all offered colors.
- `Case Material`: use `Case Material`.
- `Buttons`: use the `Buttons` list.

## CONNECTIVITY

- `WLAN + Bluetooth`: use `WLAN + Bluetooth`; normalize to `802.11xx (Wi-Fi n), Bluetooth x.x` when both standard and branded Wi-Fi generation are present.
- `WWAN`: use first non-`No support` value and append `*`.
- `Cellular Bands`: keep GSM/WCDMA/LTE/NR band rows and model-region headings.
- `NFC`: emit when the NFC row is present.
- `Wi-Fi Direct`: emit support value.
- `Wi-Fi Display`: emit support value.
- `Location Services`: use explicit location table; skip WLAN `No location service` rows and preserve WWAN/location technology rows.
- `Ports`: use `Standard Ports`; skip transfer-speed notes and preserve all physical ports.

## SECURITY & PRIVACY

- `Security`: prefer fingerprint reader details from `SECURITY & PRIVACY`; otherwise infer `Face unlock supported` from camera rows that mention face unlock.

## ACCESSORIES

- `Bundled Accessories`: use `ACCESSORIES > Bundled Accessories`; skip `None` and duplicate sublabels.

## CERTIFICATIONS

- `Green Certifications`: keep `ENERGY STAR`, `Energy rating`, `ErP Lot`, and `RoHS compliant`; strip EPREL detail sentences and append `*` to energy ratings.
- `Other Certifications`: keep `TUV/TÜV Rheinland`, `Android Enterprise Recommended`, `Hi-Res Audio`, and `MIL-STD-810H*`; ignore warranty/service/software content.
