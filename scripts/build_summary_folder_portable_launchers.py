from __future__ import annotations

import io
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


SUMMARY_LAUNCHERS = [
    {
        "bat": "run_generate_shortspec_excel_from_dir_rule_based_summary.bat",
        "release_bat": "short_spec_generator_commercial_laptops.bat",
        "title": "Lenovo Commercial Laptop ShortSpec Rule-Based Summary",
        "script": "batch_generate_shortspec_excel_rule_based.py",
        "runtime_text": "runtime_spec_text_rule_based",
        "generated_text": "generated_shortspec_batch_rule_based",
        "output": "shortspecs_rule_based_summary.xlsx",
        "extra_options": True,
    },
    {
        "bat": "run_generate_shortspec_excel_from_dir_rule_based_summary_consumer.bat",
        "release_bat": "short_spec_generator_consumer_laptops.bat",
        "title": "Lenovo Consumer Laptop ShortSpec Rule-Based Summary",
        "script": "batch_generate_shortspec_excel_rule_based_consumer.py",
        "runtime_text": "runtime_spec_text_rule_based_consumer",
        "generated_text": "generated_shortspec_batch_rule_based_consumer",
        "output": "shortspecs_rule_based_consumer_summary.xlsx",
        "extra_options": True,
    },
    {
        "bat": "run_generate_shortspec_excel_from_dir_rule_based_summary_smb.bat",
        "release_bat": "short_spec_generator_smb_laptops.bat",
        "title": "Lenovo SMB Laptop ShortSpec Rule-Based Summary",
        "script": "batch_generate_shortspec_excel_rule_based_smb.py",
        "runtime_text": "runtime_spec_text_rule_based_smb",
        "generated_text": "generated_shortspec_batch_rule_based_smb",
        "output": "shortspecs_rule_based_smb_summary.xlsx",
        "extra_options": True,
    },
    {
        "bat": "run_generate_shortspec_excel_from_dir_rule_based_summary_dt.bat",
        "release_bat": "short_spec_generator_desktop.bat",
        "title": "Lenovo Desktop ShortSpec Rule-Based Summary",
        "script": "batch_generate_shortspec_excel_rule_based_dt.py",
        "runtime_text": "runtime_spec_text_rule_based_dt",
        "generated_text": "generated_shortspec_batch_rule_based_dt",
        "output": "shortspecs_rule_based_dt_summary.xlsx",
        "extra_options": False,
    },
    {
        "bat": "run_generate_shortspec_excel_from_dir_rule_based_summary_tablet.bat",
        "release_bat": "short_spec_generator_tablet.bat",
        "title": "Lenovo Tablet ShortSpec Rule-Based Summary",
        "script": "batch_generate_shortspec_excel_rule_based_tablet.py",
        "runtime_text": "runtime_spec_text_rule_based_tablet",
        "generated_text": "generated_shortspec_batch_rule_based_tablet",
        "output": "shortspecs_rule_based_tablet_summary.xlsx",
        "extra_options": True,
    },
]


def build_launcher(config: dict[str, object]) -> str:
    extra_defaults = ""
    extra_args = ""
    if config["extra_options"]:
        extra_defaults = (
            'if not defined OUTPUT_MODE set "OUTPUT_MODE=auto"\n'
            'if not defined HEADING_STYLE set "HEADING_STYLE=modern"\n'
        )
        extra_args = ' --output-mode "%OUTPUT_MODE%" --heading-style "%HEADING_STYLE%"'

    return f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM {config["title"]} Folder Portable Launcher
REM Default behavior:
REM   - process *_Spec.PDF next to this launcher
REM   - do not scan subfolders
REM   - output one summary worksheet for all products
REM   - no local Python installation required
REM   - requires shortspec_portable_clean next to this launcher or one level above
REM ============================================================

set "LAUNCHER_DIR=%~dp0"
if not defined SOURCE_DIR set "SOURCE_DIR=%LAUNCHER_DIR%"
if not defined GLOB set "GLOB=*_Spec.PDF"
if not defined OUTPUT_XLSX set "OUTPUT_XLSX=%LAUNCHER_DIR%{config["output"]}"
if not defined WORKBOOK_LAYOUT set "WORKBOOK_LAYOUT=single_sheet_summary"
{extra_defaults}set "SHORTSPEC_RUNTIME_TEXT={config["runtime_text"]}"
set "SHORTSPEC_GENERATED_TEXT={config["generated_text"]}"
set "SHORTSPEC_SCRIPT_NAME={config["script"]}"
set "EXIT_CODE=1"

for %%I in ("%SOURCE_DIR%\\.") do set "SOURCE_DIR=%%~fI"

if defined PACKAGE_DIR (
  for %%I in ("%PACKAGE_DIR%\\.") do set "PACKAGE_DIR=%%~fI"
) else (
  set "PACKAGE_DIR=%LAUNCHER_DIR%shortspec_portable_clean"
  if not exist "!PACKAGE_DIR!\\python-runtime\\python.exe" (
    set "PACKAGE_DIR=%LAUNCHER_DIR%..\\shortspec_portable_clean"
  )
)

if not exist "%PACKAGE_DIR%\\python-runtime\\python.exe" (
  echo ERROR: Could not find portable runtime.
  echo Expected shortspec_portable_clean next to this launcher or one level above it.
  echo You can also set PACKAGE_DIR to the shortspec_portable_clean path.
  goto :finish
)

if not exist "%PACKAGE_DIR%\\scripts\\%SHORTSPEC_SCRIPT_NAME%" (
  echo ERROR: Missing generator script:
  echo %PACKAGE_DIR%\\scripts\\%SHORTSPEC_SCRIPT_NAME%
  goto :finish
)

set "PYTHON_EXE=%PACKAGE_DIR%\\python-runtime\\python.exe"
set "RUNTIME_TEXT_DIR=%SOURCE_DIR%\\analysis_output\\%SHORTSPEC_RUNTIME_TEXT%"
set "GENERATED_TEXT_DIR=%SOURCE_DIR%\\analysis_output\\%SHORTSPEC_GENERATED_TEXT%"
set "PYTHONUTF8=1"

echo {config["title"]}
echo Source: %SOURCE_DIR%
echo Glob: %GLOB%
echo Output: %OUTPUT_XLSX%
echo Runtime: %PACKAGE_DIR%
echo.

set "SPEC_COUNT=0"
for %%F in ("%SOURCE_DIR%\\%GLOB%") do (
  if exist "%%~fF" set /a SPEC_COUNT+=1
)
echo Found !SPEC_COUNT! spec file(s).
if "!SPEC_COUNT!"=="0" (
  echo ERROR: No spec files found.
  goto :finish
)

echo Starting generator...
echo.
pushd "%PACKAGE_DIR%\\scripts"
"%PYTHON_EXE%" ".\\%SHORTSPEC_SCRIPT_NAME%" --spec-dir "%SOURCE_DIR%" --glob "%GLOB%" --output-xlsx "%OUTPUT_XLSX%" --workbook-layout "%WORKBOOK_LAYOUT%"{extra_args} --runtime-text-dir "%RUNTIME_TEXT_DIR%" --generated-text-dir "%GENERATED_TEXT_DIR%"
set "EXIT_CODE=%ERRORLEVEL%"
popd

if "%EXIT_CODE%"=="0" if not "%KEEP_SPEC_FILES%"=="1" (
  echo.
  echo Deleting processed source spec files...
  for %%F in ("%SOURCE_DIR%\\%GLOB%") do (
    if exist "%%~fF" (
      echo DELETE_SOURCE_SPEC	%%~fF
      del /f /q "%%~fF" >nul 2>nul
    )
  )
)

:finish
echo.
if "%EXIT_CODE%"=="0" (
  echo Completed successfully.
  echo Output: %OUTPUT_XLSX%
) else (
  echo Failed with exit code %EXIT_CODE%.
)
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
"""


def release_dir_for_today(repo_root: Path) -> Path:
    return repo_root / "release" / f"short_spec_generator_{datetime.now():%y%m%d}"


def find_runtime_source(repo_root: Path, target_runtime: Path) -> Path | None:
    candidates = [repo_root / "shortspec_portable_clean", target_runtime]
    release_root = repo_root / "release"
    if release_root.exists():
        for release_dir in sorted(release_root.glob("short_spec_generator_*"), reverse=True):
            candidates.append(release_dir / "shortspec_portable_clean")

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "python-runtime" / "python.exe").exists():
            return resolved
    return None


def build_python_runtime(target_runtime: Path) -> None:
    from portable_python_runtime import build_portable_python_runtime

    python_runtime = target_runtime / "python-runtime"
    if python_runtime.exists():
        shutil.rmtree(python_runtime)
    python_runtime.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(build_portable_python_runtime())) as runtime_zip:
        runtime_zip.extractall(python_runtime)


def sync_runtime(repo_root: Path, target_runtime: Path) -> None:
    target_runtime.mkdir(parents=True, exist_ok=True)
    runtime_source = find_runtime_source(repo_root, target_runtime)

    if runtime_source is None:
        build_python_runtime(target_runtime)
    else:
        source_python = runtime_source / "python-runtime"
        target_python = target_runtime / "python-runtime"
        if source_python.resolve() != target_python.resolve():
            if target_python.exists():
                shutil.rmtree(target_python)
            shutil.copytree(source_python, target_python)

    for folder_name in ("scripts", "prompts"):
        source = repo_root / folder_name
        target = target_runtime / folder_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)

    (target_runtime / "README_clean_portable.txt").write_text(
        "\n".join(
            [
                "ShortSpec folder portable runtime.",
                "",
                "Use the summary .bat files in the parent release folder.",
                "Keep this folder next to those .bat files.",
                "Do not edit generated .bat files by hand; rebuild them from scripts/build_summary_folder_portable_launchers.py.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\r\n",
    )


def write_release_readme(target_dir: Path) -> None:
    (target_dir / "README_green_portable.txt").write_text(
        "\n".join(
            [
                "ShortSpec Generator portable release.",
                "",
                "Copy this whole folder to another PC, then put full spec PDFs next to the required .bat launcher.",
                "Run the matching summary .bat file. The output workbook is written next to the launcher.",
                "",
                "Delivered launchers:",
                "- short_spec_generator_commercial_laptops.bat",
                "- short_spec_generator_consumer_laptops.bat",
                "- short_spec_generator_smb_laptops.bat",
                "- short_spec_generator_desktop.bat",
                "- short_spec_generator_tablet.bat",
                "",
                "The shortspec_portable_clean folder is required and must stay next to the launchers.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\r\n",
    )


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    target_dir = release_dir_for_today(repo_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    sync_runtime(repo_root, target_dir / "shortspec_portable_clean")
    write_release_readme(target_dir)
    (target_dir / ".shortspec_green_portable_package").write_text("folder_portable_summary_only\n", encoding="utf-8")

    for config in SUMMARY_LAUNCHERS:
        content = build_launcher(config)
        target = target_dir / str(config["release_bat"])
        target.write_text(content, encoding="utf-8", newline="\r\n")
        print(target)


if __name__ == "__main__":
    main()
