# AGENTS.md

This file defines project-specific working rules for agents contributing to this repository.

## Project Direction

- The current primary technical route is HTML source input.
- PDF-based tools are historical deliverables and references. Do not treat PDF as the preferred route for new feature development unless explicitly requested.
- The current core short-spec feature set is Storage, WLAN, and Display.
- Storage, WLAN, and Display HTML rules are considered established unless the user explicitly requests a rule change.
- Other short-spec features are under active development and should reuse the existing extraction, rule-based conversion, Excel output, launcher, and release packaging patterns where practical.

## Completed Deliverables

The project has the following milestone deliverables:

- Full short-spec generation tools using PDF source input.
- Storage, WLAN, and Display short-spec generation tools using PDF source input.
- Storage, WLAN, and Display short-spec generation tools using HTML source input.

Do not modify completed deliverables, historical release folders, or existing rules unless the user explicitly asks for that scope.

## Rule Maintenance

- Do not invent, simplify, or rewrite business rules without explicit user instruction.
- When a rule change is requested, keep the change narrowly scoped to the affected feature and product lines.
- Preserve existing behavior for unrelated features and product lines.
- If a rule depends on source wording such as `each`, `total`, `hardware ready`, `None`, or product-line-specific conditions, keep that distinction explicit in implementation and tests.
- Do not use ad hoc string changes when an existing parser, normalizer, or shared helper already handles the rule family.

## HTML Source Assumptions

- Product names are extracted from `div.titleProductName`.
- Full specification content is extracted from `div.spec-content`.
- HTML and PDF source information are expected to be semantically consistent, but HTML is cleaner for structured extraction and is the main source format going forward.
- For HTML table-backed rules, prefer table headers and field values over positional or visual assumptions.

## Feature-Specific Status

- Storage HTML rules are established, including Max Storage Support handling, RAID extraction, M.2 size removal, `each` versus `total` capacity calculation, condition-branch selection, UFS normalization, and microSD formatting.
- WLAN HTML rules are established, including highest Wi-Fi selection, Bluetooth version selection, optional WLAN handling, Intel tie-breaking, and Bluetooth hardware-ready output.
- Display HTML rules are established and should follow HTML table fields strictly.
- ThinkStation Storage uses Max Storage Support directly and must not be converted through the non-ThinkStation Storage summarization rules.

## Release Packaging

- The package root should contain launcher `.bat` files and final generated `.xlsx` workbooks after a successful run.
- HTML source files are placed in the package root next to the launchers, and launchers should delete root-level source HTML files after successful generation.
- Put runtime files in `rt`, process files and manifests in `_work`, documentation in `docs`, and package metadata in `_meta`.
- Keep release filenames short enough to avoid Windows path-length issues after extraction.
- Integrated Storage/WLAN/Display deliverables should write all feature outputs into one Excel workbook, not separate workbooks.
- When updating a release folder, sync the changed runtime scripts into the release `rt/scripts` directory.
- When updating a release zip, preserve the original zip structure and avoid adding local test outputs, temporary Excel files, copied source specs, or analysis artifacts.

## Verification

- After rule changes, validate with representative normal samples, known historical error samples, and edge cases for the changed rule.
- Verify the final generated Excel content, not only console logs or intermediate manifests.
- For HTML integrated deliverables, run the relevant `.bat` launcher when feasible.
- Run Python compile checks for changed common scripts and affected product-line launch scripts.

## Operational Boundaries

- Do not run git operations unless explicitly requested.
- Do not revert or overwrite unrelated user changes.
- Do not modify unrelated deliverables or rules while fixing a specific feature.
- Keep generated verification outputs under an analysis or temporary output folder, and do not include them in release zips.
- Use `apply_patch` for manual file edits.
