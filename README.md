# Short Spec Generator

Rule-based batch tools for converting full product specification PDFs into short specification Excel summaries.

## Layout

- `scripts/`: source scripts and build utilities.
- `prompts/`: conversion prompts and product-family rule notes.
- `docs/`: project notes and requirements.
- `data/`: local reference PDFs and training data. This directory is ignored by Git.
- `release/`: dated delivery packages. This directory is ignored by Git; publish these through a release channel rather than committing the runtime bundle.

## Delivery Format

New deliveries should be placed under:

```text
release/short_spec_generator_YYMMDD/
```

Only the summary launcher `.bat` files are delivered at the package top level:

- `short_spec_generator_commercial_laptops.bat`
- `short_spec_generator_consumer_laptops.bat`
- `short_spec_generator_smb_laptops.bat`
- `short_spec_generator_desktop.bat`
- `short_spec_generator_tablet.bat`

The launchers expect the sibling `shortspec_portable_clean/` runtime folder from the same release package.

To rebuild the current date package, run:

```powershell
python scripts\build_summary_folder_portable_launchers.py
```

## Development Notes

For local development, run the Python scripts in `scripts/` directly and pass explicit input/output paths. The release launchers are generated artifacts and should not be edited by hand.
