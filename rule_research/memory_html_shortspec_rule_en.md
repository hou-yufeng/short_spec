# Memory HTML ShortSpec Rule Report

## 1. Memory HTML Spec Content Classification

Memory information is extracted from HTML blocks under `div specstructure="Memory"`.
The core source fields are:

| Field | Purpose |
|---|---|
| `Max Memory` | Main source for capacity, soldered / not upgradable wording, and condition branches |
| `Memory Slots` | Primary field for identifying the memory structure and selecting the generation path |
| `Memory Type` | Source for memory type, native speed, and Memory Type notes |
| `Memory Protection` | Not used by the current Memory short-spec rule |

Based on the current `data/sample` set, Memory HTML specs can be classified as:

| Category | Identification Rule | Handling Direction |
|---|---|---|
| Upgradeable slot memory | `Memory Slots` does not mention `systemboard` or `soldered` | Output slot structure plus full `Max Memory` |
| Soldered / systemboard memory only | `Memory Slots` mentions `systemboard` or `soldered`, and has no usable slot | Output the highest-capacity soldered memory branch; add native speed only when needed |
| Soldered memory plus usable slot | `Memory Slots` mentions `systemboard` or `soldered`, and also has usable `slot(s)` | Output soldered branch and upgradeable-slot branch separately |
| ThinkStation | Product name starts with `ThinkStation` | Use `Max Memory` directly |

## 2. Processing Difficulties and Problems to Solve

1. HTML value shapes are inconsistent.
   Some fields are single `<span>` values, while others are multi-option `<ul><li>` lists.

2. `Max Memory` may contain condition branches.
   Examples include platform branches such as `Lunar Lake:` / `Arrow Lake:` or ECC / Non-ECC branches.

3. `Memory Slots` needs semantic parsing.
   The phrase `no slots` contains the word `slots`, so usable slot detection cannot rely on a simple substring check.

4. `Max Memory` may already include memory type and speed.
   Examples include `LPDDR5X-8533`, `DDR5-5600`, `SODIMM`, `CUDIMM`, `RDIMM`, and `LPCAMM2`.
   In these cases, appending `Memory Type` would duplicate information.

5. `Memory Type` may contain multiple speeds or multiple memory types.
   For the same memory type, the highest speed should be selected.
   If multiple memory types exist, the highest speed for each type should be retained.

6. Notes are reference-based, not plain field text.
   Notes must be extracted by matching `supText` note numbers from `Memory Type` or its options to the corresponding note content.

7. Notes must not be mixed into the Memory short spec.
   In the current baseline, notes are written to the Excel `Note` field.

## 3. Solution Approach

The rule uses `Memory Slots` as the first decision point, then applies the appropriate logic to `Max Memory` and `Memory Type`.

- `Memory Slots` determines whether the product is upgradeable, soldered-only, mixed soldered-plus-slot, or ThinkStation.
- `Max Memory` is the primary capacity source.
- For multi-option `Max Memory`, the highest-capacity branch is selected when the rule requires a single branch.
- `Memory Type` is only used when native speed or missing type information must be supplemented.
- Condition branches are detected by the `xxxx:` prefix format.
- Memory Type notes are extracted, deduplicated, and written to the Excel `Note` field.
- `Memory Protection` is ignored.

## 4. Memory ShortSpec Generation Logic

### 4.1 Common Rules

1. Extract the following fields from `div specstructure="Memory"`:
   - `Max Memory`
   - `Memory Slots`
   - `Memory Type`

2. Ignore `Memory Protection`.

3. Extract notes only from:
   - `Memory Type` heading notes
   - `Memory Type` option notes

4. Write extracted note text to the Excel `Note` field.
   Do not append notes to the `Short Spec` field.

### 4.2 ThinkStation

For products whose name starts with `ThinkStation`:

```text
Short Spec = Max Memory
```

Rules:

- Use `Max Memory` directly.
- Do not normalize `Up to`.
- Do not append `Memory Type`.
- Write Memory Type notes to the `Note` field.

### 4.3 Memory Slots Without `systemboard` or `soldered`

Condition:

```text
Memory Slots does not mention systemboard or soldered
```

Generation logic:

1. Take the text before the first comma from `Memory Slots`.
   If there is no comma, take the full value.
2. Take the full `Max Memory` value.
3. If `Max Memory` starts with `Up to`, change `U` to lowercase.

Output format:

```text
{Memory Slots first part}, {Max Memory}
```

### 4.4 Soldered / Systemboard Memory Only

Condition:

```text
Memory Slots mentions systemboard or soldered, and has no usable slot
```

Generation logic:

1. Select the highest-capacity branch from `Max Memory`.
2. Remove the condition prefix if present.
   For example, remove `Lunar Lake:`.
3. Prefix the result with `Up to`.
4. If the selected `Max Memory` already contains a memory type, do not append `Memory Type`.
5. If the selected `Max Memory` does not contain a memory type, add a separate line:

```text
Memory native speed up to {highest Memory Type speed}
```

### 4.5 Soldered / Systemboard Memory Plus Usable Slot

Condition:

```text
Memory Slots mentions systemboard or soldered, and also has usable slot(s)
```

Generation logic:

1. Select the highest-capacity `Max Memory` branch that contains `not upgradable` or `soldered`.
   - Keep the condition prefix if present.
   - Prefix the branch body with `up to`.
   - Output this as one item.

2. Select the highest-capacity `Max Memory` branch that does not contain `not upgradable` or `soldered`.
   - Keep the condition prefix if present.
   - If the branch body does not start with `Up to` or `up to`, prefix it with `up to`.

3. Match the selected non-soldered branch to the corresponding `Memory Slots` condition branch.

4. Take the corresponding `Memory Slots` text before the first comma.
   If there is no comma, take the full value.

5. Output the slot branch as:

```text
{Memory Slots first part}, {Max Memory branch}
```

The soldered branch and slot branch are output as separate lines.

### 4.6 Excel Output Contract

The current baseline delivery is `mkosc_html_260706`.

The generated Excel columns are:

```text
Product / L1 Feature / L2 Feature / Short Spec / Note
```

Memory output rules:

- Memory short spec is written to `Short Spec`.
- Memory Type note is written to `Note`.
- Notes are not appended to `Short Spec`.
- Future feature-level notes should also use the same `Note` field.
