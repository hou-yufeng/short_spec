from __future__ import annotations

import io
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


WLAN_LAUNCHERS = [
    {
        "release_bat": "wlan_short_spec_generator_commercial_laptops.bat",
        "title": "Lenovo Commercial Laptop WLAN ShortSpec",
        "script": "batch_generate_wlan_shortspec_excel_rule_based.py",
        "runtime_text": "runtime_spec_text_wlan_rule_based_commercial",
        "generated_text": "generated_wlan_shortspec_rule_based_commercial",
        "output": "wlan_shortspecs_rule_based_commercial_summary.xlsx",
    },
    {
        "release_bat": "wlan_short_spec_generator_consumer_laptops.bat",
        "title": "Lenovo Consumer Laptop WLAN ShortSpec",
        "script": "batch_generate_wlan_shortspec_excel_rule_based_consumer.py",
        "runtime_text": "runtime_spec_text_wlan_rule_based_consumer",
        "generated_text": "generated_wlan_shortspec_rule_based_consumer",
        "output": "wlan_shortspecs_rule_based_consumer_summary.xlsx",
    },
    {
        "release_bat": "wlan_short_spec_generator_tablet.bat",
        "title": "Lenovo Tablet WLAN ShortSpec",
        "script": "batch_generate_wlan_shortspec_excel_rule_based_tablet.py",
        "runtime_text": "runtime_spec_text_wlan_rule_based_tablet",
        "generated_text": "generated_wlan_shortspec_rule_based_tablet",
        "output": "wlan_shortspecs_rule_based_tablet_summary.xlsx",
    },
    {
        "release_bat": "wlan_short_spec_generator_desktop.bat",
        "title": "Lenovo Desktop WLAN ShortSpec",
        "script": "batch_generate_wlan_shortspec_excel_rule_based_dt.py",
        "runtime_text": "runtime_spec_text_wlan_rule_based_dt",
        "generated_text": "generated_wlan_shortspec_rule_based_dt",
        "output": "wlan_shortspecs_rule_based_dt_summary.xlsx",
    },
    {
        "release_bat": "wlan_short_spec_generator_thinkstation.bat",
        "title": "Lenovo ThinkStation WLAN ShortSpec",
        "script": "batch_generate_wlan_shortspec_excel_rule_based_thinkstation.py",
        "runtime_text": "runtime_spec_text_wlan_rule_based_thinkstation",
        "generated_text": "generated_wlan_shortspec_rule_based_thinkstation",
        "output": "wlan_shortspecs_rule_based_thinkstation_summary.xlsx",
    },
    {
        "release_bat": "wlan_short_spec_generator_smb.bat",
        "title": "Lenovo SMB WLAN ShortSpec",
        "script": "batch_generate_wlan_shortspec_excel_rule_based_smb.py",
        "runtime_text": "runtime_spec_text_wlan_rule_based_smb",
        "generated_text": "generated_wlan_shortspec_rule_based_smb",
        "output": "wlan_shortspecs_rule_based_smb_summary.xlsx",
    },
]


def ensure_inside(path: Path, root: Path) -> None:
    path_resolved = path.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        common = os.path.commonpath([str(path_resolved), str(root_resolved)])
    except ValueError as exc:
        raise RuntimeError(f"Refusing to operate outside {root_resolved}: {path_resolved}") from exc
    if os.path.normcase(common) != os.path.normcase(str(root_resolved)):
        raise RuntimeError(f"Refusing to operate outside {root_resolved}: {path_resolved}")


def safe_rmtree(path: Path, root: Path) -> None:
    if path.exists():
        ensure_inside(path, root)
        shutil.rmtree(path)


def build_launcher(config: dict[str, str]) -> str:
    return f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM {config["title"]} Folder Portable Launcher
REM Default behavior:
REM   - process *_Spec.PDF next to this launcher
REM   - do not scan subfolders
REM   - output one WLAN-only summary worksheet for all products
REM   - no local Python installation required
REM   - requires shortspec_portable_clean next to the launcher or one level above
REM ============================================================

set "LAUNCHER_DIR=%~dp0"
if not defined SOURCE_DIR set "SOURCE_DIR=%LAUNCHER_DIR%"
if not defined GLOB set "GLOB=*_Spec.PDF"
if not defined OUTPUT_XLSX set "OUTPUT_XLSX=%LAUNCHER_DIR%{config["output"]}"
if not defined WORKBOOK_LAYOUT set "WORKBOOK_LAYOUT=single_sheet_summary"
set "SHORTSPEC_RUNTIME_TEXT={config["runtime_text"]}"
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
set "WLAN_VENDOR_DEPS=%PACKAGE_DIR%\\scripts\\_wlan_pdf_deps"
if exist "%WLAN_VENDOR_DEPS%\\pypdf" (
  if defined PYTHONPATH (
    set "PYTHONPATH=%WLAN_VENDOR_DEPS%;%PYTHONPATH%"
  ) else (
    set "PYTHONPATH=%WLAN_VENDOR_DEPS%"
  )
)

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
"%PYTHON_EXE%" ".\\%SHORTSPEC_SCRIPT_NAME%" --spec-dir "%SOURCE_DIR%" --glob "%GLOB%" --output-xlsx "%OUTPUT_XLSX%" --workbook-layout "%WORKBOOK_LAYOUT%" --runtime-text-dir "%RUNTIME_TEXT_DIR%" --generated-text-dir "%GENERATED_TEXT_DIR%"
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
    return repo_root / "release" / f"wlan_short_spec_generator_{datetime.now():%y%m%d}"


def find_runtime_source(repo_root: Path, target_runtime: Path) -> Path | None:
    candidates = [repo_root / "shortspec_portable_clean", target_runtime]
    release_root = repo_root / "release"
    if release_root.exists():
        for pattern in ("wlan_short_spec_generator_*", "display_short_spec_generator_*", "short_spec_generator_*"):
            for release_dir in sorted(release_root.glob(pattern), reverse=True):
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
    safe_rmtree(python_runtime, target_runtime)
    python_runtime.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(build_portable_python_runtime())) as runtime_zip:
        runtime_zip.extractall(python_runtime)


def sync_wlan_pdf_deps(repo_root: Path, target_runtime: Path) -> None:
    target_vendor = target_runtime / "scripts" / "_wlan_pdf_deps"
    safe_rmtree(target_vendor, target_runtime)

    for candidate in (repo_root / "analysis_output" / "pdf_deps", repo_root / "pdf_deps"):
        if (candidate / "pypdf").exists():
            shutil.copytree(candidate, target_vendor)
            return


def sync_runtime(repo_root: Path, target_runtime: Path) -> None:
    target_runtime.mkdir(parents=True, exist_ok=True)
    runtime_source = find_runtime_source(repo_root, target_runtime)

    if runtime_source is None:
        build_python_runtime(target_runtime)
    else:
        source_python = runtime_source / "python-runtime"
        target_python = target_runtime / "python-runtime"
        if source_python.resolve() != target_python.resolve():
            safe_rmtree(target_python, target_runtime)
            shutil.copytree(source_python, target_python)

    for folder_name in ("scripts", "prompts"):
        source = repo_root / folder_name
        target = target_runtime / folder_name
        safe_rmtree(target, target_runtime)
        shutil.copytree(source, target)

    sync_wlan_pdf_deps(repo_root, target_runtime)


def write_release_readme(target_dir: Path) -> None:
    (target_dir / "README_wlan_portable.txt").write_text(
        "\r\n".join(
            [
                "WLAN ShortSpec Generator portable release.",
                "",
                "Copy this whole folder to another PC, then put full spec PDFs next to the required .bat launcher.",
                "Run the matching WLAN .bat file. The output workbook is written next to the launcher.",
                "",
                "Delivered launchers:",
                "- wlan_short_spec_generator_commercial_laptops.bat",
                "- wlan_short_spec_generator_consumer_laptops.bat",
                "- wlan_short_spec_generator_tablet.bat",
                "- wlan_short_spec_generator_desktop.bat",
                "- wlan_short_spec_generator_thinkstation.bat",
                "- wlan_short_spec_generator_smb.bat",
                "",
                "The shortspec_portable_clean folder is required and must stay next to the launchers.",
                "The launcher deletes processed source PDFs after a successful run, matching the existing portable behavior.",
                "Set KEEP_SPEC_FILES=1 before running the launcher if source PDFs must be retained.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\r\n",
    )


def zip_release(target_dir: Path) -> Path:
    zip_path = target_dir.with_suffix(".zip")
    ensure_inside(zip_path, target_dir.parent)
    if zip_path.exists():
        zip_path.unlink()

    generated_workbooks = {config["output"] for config in WLAN_LAUNCHERS}
    generated_outputs = set(generated_workbooks)
    generated_outputs.update(Path(name).with_suffix(".json").name for name in generated_workbooks)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in target_dir.rglob("*"):
            if path.is_dir():
                continue
            relative = path.relative_to(target_dir)
            if path.name.startswith("~$"):
                continue
            if relative.parts and relative.parts[0] == "analysis_output":
                continue
            if len(relative.parts) == 1 and path.name in generated_outputs:
                continue
            archive.write(path, Path(target_dir.name, relative).as_posix())

    return zip_path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    target_dir = release_dir_for_today(repo_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    sync_runtime(repo_root, target_dir / "shortspec_portable_clean")
    write_release_readme(target_dir)
    (target_dir / ".wlan_shortspec_portable_package").write_text(
        "folder_portable_wlan_only\n",
        encoding="utf-8",
    )

    for config in WLAN_LAUNCHERS:
        content = build_launcher(config)
        target = target_dir / config["release_bat"]
        target.write_text(content, encoding="utf-8", newline="\r\n")
        print(target)

    print(zip_release(target_dir))


if __name__ == "__main__":
    main()
