from __future__ import annotations

import io
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


COMBINED_LAUNCHERS = [
    {
        "release_bat": "sdw_com.bat",
        "title": "Lenovo Commercial Laptop Storage Display Wi-Fi ShortSpec",
        "combined_output": "sdw_com.xlsx",
        "storage_script": "batch_generate_storage_shortspec_excel_rule_based.py",
        "display_script": "batch_generate_display_shortspec_excel_rule_based.py",
        "wlan_script": "batch_generate_wlan_shortspec_excel_rule_based.py",
        "storage_runtime_text": "runtime_spec_text_storage_rule_based_commercial",
        "display_runtime_text": "runtime_spec_text_display_rule_based_commercial",
        "wlan_runtime_text": "runtime_spec_text_wlan_rule_based_commercial",
        "storage_generated_text": "generated_storage_shortspec_rule_based_commercial",
        "display_generated_text": "generated_display_shortspec_rule_based_commercial",
        "wlan_generated_text": "generated_wlan_shortspec_rule_based_commercial",
    },
    {
        "release_bat": "sdw_con.bat",
        "title": "Lenovo Consumer Laptop Storage Display Wi-Fi ShortSpec",
        "combined_output": "sdw_con.xlsx",
        "storage_script": "batch_generate_storage_shortspec_excel_rule_based_consumer.py",
        "display_script": "batch_generate_display_shortspec_excel_rule_based_consumer.py",
        "wlan_script": "batch_generate_wlan_shortspec_excel_rule_based_consumer.py",
        "storage_runtime_text": "runtime_spec_text_storage_rule_based_consumer",
        "display_runtime_text": "runtime_spec_text_display_rule_based_consumer",
        "wlan_runtime_text": "runtime_spec_text_wlan_rule_based_consumer",
        "storage_generated_text": "generated_storage_shortspec_rule_based_consumer",
        "display_generated_text": "generated_display_shortspec_rule_based_consumer",
        "wlan_generated_text": "generated_wlan_shortspec_rule_based_consumer",
    },
    {
        "release_bat": "sdw_smb.bat",
        "title": "Lenovo SMB Laptop Storage Display Wi-Fi ShortSpec",
        "combined_output": "sdw_smb.xlsx",
        "storage_script": "batch_generate_storage_shortspec_excel_rule_based_smb.py",
        "display_script": "batch_generate_display_shortspec_excel_rule_based_smb.py",
        "wlan_script": "batch_generate_wlan_shortspec_excel_rule_based_smb.py",
        "storage_runtime_text": "runtime_spec_text_storage_rule_based_smb",
        "display_runtime_text": "runtime_spec_text_display_rule_based_smb",
        "wlan_runtime_text": "runtime_spec_text_wlan_rule_based_smb",
        "storage_generated_text": "generated_storage_shortspec_rule_based_smb",
        "display_generated_text": "generated_display_shortspec_rule_based_smb",
        "wlan_generated_text": "generated_wlan_shortspec_rule_based_smb",
    },
    {
        "release_bat": "sdw_tab.bat",
        "title": "Lenovo Tablet Storage Display Wi-Fi ShortSpec",
        "combined_output": "sdw_tab.xlsx",
        "storage_script": "batch_generate_storage_shortspec_excel_rule_based_tablet.py",
        "display_script": "batch_generate_display_shortspec_excel_rule_based_tablet.py",
        "wlan_script": "batch_generate_wlan_shortspec_excel_rule_based_tablet.py",
        "storage_runtime_text": "runtime_spec_text_storage_rule_based_tablet",
        "display_runtime_text": "runtime_spec_text_display_rule_based_tablet",
        "wlan_runtime_text": "runtime_spec_text_wlan_rule_based_tablet",
        "storage_generated_text": "generated_storage_shortspec_rule_based_tablet",
        "display_generated_text": "generated_display_shortspec_rule_based_tablet",
        "wlan_generated_text": "generated_wlan_shortspec_rule_based_tablet",
    },
    {
        "release_bat": "sdw_dt.bat",
        "title": "Lenovo Desktop Storage Display Wi-Fi ShortSpec",
        "combined_output": "sdw_dt.xlsx",
        "storage_script": "batch_generate_storage_shortspec_excel_rule_based_dt.py",
        "display_script": "batch_generate_display_shortspec_excel_rule_based_dt.py",
        "wlan_script": "batch_generate_wlan_shortspec_excel_rule_based_dt.py",
        "storage_runtime_text": "runtime_spec_text_storage_rule_based_dt",
        "display_runtime_text": "runtime_spec_text_display_rule_based_dt",
        "wlan_runtime_text": "runtime_spec_text_wlan_rule_based_dt",
        "storage_generated_text": "generated_storage_shortspec_rule_based_dt",
        "display_generated_text": "generated_display_shortspec_rule_based_dt",
        "wlan_generated_text": "generated_wlan_shortspec_rule_based_dt",
    },
    {
        "release_bat": "sw_ts.bat",
        "title": "Lenovo ThinkStation Storage Wi-Fi ShortSpec",
        "combined_output": "sw_ts.xlsx",
        "storage_script": "batch_generate_storage_shortspec_excel_rule_based_thinkstation.py",
        "wlan_script": "batch_generate_wlan_shortspec_excel_rule_based_thinkstation.py",
        "storage_runtime_text": "runtime_spec_text_storage_rule_based_thinkstation",
        "wlan_runtime_text": "runtime_spec_text_wlan_rule_based_thinkstation",
        "storage_generated_text": "generated_storage_shortspec_rule_based_thinkstation",
        "wlan_generated_text": "generated_wlan_shortspec_rule_based_thinkstation",
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


def ignore_generated_files(_directory: str, names: list[str]) -> list[str]:
    return [
        name
        for name in names
        if name == "__pycache__" or name.endswith((".pyc", ".pyo"))
    ]


def optional_display_blocks(config: dict[str, str]) -> dict[str, str]:
    if "display_script" not in config:
        return {
            "script_assignment": "",
            "temp_output": "",
            "script_check": "",
            "vendor_deps": "",
            "run_feature": "",
            "merge_arg": "",
        }

    return {
        "script_assignment": f'set "DISPLAY_SCRIPT_NAME={config["display_script"]}"\n',
        "temp_output": 'set "DISPLAY_OUTPUT_XLSX=%TEMP_OUTPUT_DIR%\\dp.xlsx"\n',
        "script_check": (
            'if not exist "%PACKAGE_DIR%\\scripts\\%DISPLAY_SCRIPT_NAME%" (\n'
            "  echo ERROR: Missing generator script:\n"
            "  echo %PACKAGE_DIR%\\scripts\\%DISPLAY_SCRIPT_NAME%\n"
            "  goto :finish\n"
            ")\n"
        ),
        "vendor_deps": (
            'set "DISPLAY_VENDOR_DEPS=%PACKAGE_DIR%\\scripts\\_display_pdf_deps"\n'
            'if exist "%DISPLAY_VENDOR_DEPS%\\pypdf" (\n'
            '  if defined PYTHONPATH (set "PYTHONPATH=%DISPLAY_VENDOR_DEPS%;%PYTHONPATH%") else (set "PYTHONPATH=%DISPLAY_VENDOR_DEPS%")\n'
            ")\n"
        ),
        "run_feature": (
            f'call :run_feature "Display" "%DISPLAY_SCRIPT_NAME%" "{config["display_runtime_text"]}" '
            f'"{config["display_generated_text"]}" "%DISPLAY_OUTPUT_XLSX%"\n'
            "if errorlevel 1 goto :finish\n"
        ),
        "merge_arg": ' --feature "Display" "%DISPLAY_OUTPUT_XLSX%"',
    }


def build_launcher(config: dict[str, str]) -> str:
    display = optional_display_blocks(config)
    feature_text = "Storage, Display, and WLAN" if "display_script" in config else "Storage and WLAN"

    return f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM {config["title"]} Folder Portable Launcher
REM Default behavior:
REM   - process *_Spec.PDF next to this launcher
REM   - do not scan subfolders
REM   - generate one combined {feature_text} workbook
REM   - no local Python installation required
REM   - requires rt next to this launcher or one level above
REM ============================================================

set "LAUNCHER_DIR=%~dp0"
if not defined SOURCE_DIR set "SOURCE_DIR=%LAUNCHER_DIR%"
if not defined OUTPUT_DIR set "OUTPUT_DIR=%LAUNCHER_DIR%"
if not defined GLOB set "GLOB=*_Spec.PDF"
if not defined WORKBOOK_LAYOUT set "WORKBOOK_LAYOUT=single_sheet_summary"
set "STORAGE_SCRIPT_NAME={config["storage_script"]}"
{display["script_assignment"]}set "WLAN_SCRIPT_NAME={config["wlan_script"]}"
set "MERGE_SCRIPT_NAME=merge_feature_workbooks.py"
set "EXIT_CODE=1"

for %%I in ("%SOURCE_DIR%\\.") do set "SOURCE_DIR=%%~fI"
for %%I in ("%OUTPUT_DIR%\\.") do set "OUTPUT_DIR=%%~fI"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if errorlevel 1 goto :finish
if not defined COMBINED_OUTPUT_XLSX set "COMBINED_OUTPUT_XLSX=%OUTPUT_DIR%\\{config["combined_output"]}"
set "TEMP_OUTPUT_DIR=%OUTPUT_DIR%\\analysis_output\\sdw_tmp_%RANDOM%%RANDOM%"
if not exist "%TEMP_OUTPUT_DIR%" mkdir "%TEMP_OUTPUT_DIR%"
if errorlevel 1 goto :finish
set "STORAGE_OUTPUT_XLSX=%TEMP_OUTPUT_DIR%\\st.xlsx"
{display["temp_output"]}set "WLAN_OUTPUT_XLSX=%TEMP_OUTPUT_DIR%\\wf.xlsx"

if defined PACKAGE_DIR (
  for %%I in ("%PACKAGE_DIR%\\.") do set "PACKAGE_DIR=%%~fI"
) else (
  set "PACKAGE_DIR=%LAUNCHER_DIR%rt"
  if not exist "!PACKAGE_DIR!\\python-runtime\\python.exe" (
    set "PACKAGE_DIR=%LAUNCHER_DIR%..\\rt"
  )
)

if not exist "%PACKAGE_DIR%\\python-runtime\\python.exe" (
  echo ERROR: Could not find portable runtime.
  echo Expected rt next to this launcher or one level above it.
  echo You can also set PACKAGE_DIR to the rt path.
  goto :finish
)

if not exist "%PACKAGE_DIR%\\scripts\\%STORAGE_SCRIPT_NAME%" (
  echo ERROR: Missing generator script:
  echo %PACKAGE_DIR%\\scripts\\%STORAGE_SCRIPT_NAME%
  goto :finish
)
{display["script_check"]}if not exist "%PACKAGE_DIR%\\scripts\\%WLAN_SCRIPT_NAME%" (
  echo ERROR: Missing generator script:
  echo %PACKAGE_DIR%\\scripts\\%WLAN_SCRIPT_NAME%
  goto :finish
)
if not exist "%PACKAGE_DIR%\\scripts\\%MERGE_SCRIPT_NAME%" (
  echo ERROR: Missing merge script:
  echo %PACKAGE_DIR%\\scripts\\%MERGE_SCRIPT_NAME%
  goto :finish
)

set "PYTHON_EXE=%PACKAGE_DIR%\\python-runtime\\python.exe"
set "PYTHONUTF8=1"

set "STORAGE_VENDOR_DEPS=%PACKAGE_DIR%\\scripts\\_storage_pdf_deps"
if exist "%STORAGE_VENDOR_DEPS%\\pypdf" (
  if defined PYTHONPATH (set "PYTHONPATH=%STORAGE_VENDOR_DEPS%;%PYTHONPATH%") else (set "PYTHONPATH=%STORAGE_VENDOR_DEPS%")
)
{display["vendor_deps"]}set "WLAN_VENDOR_DEPS=%PACKAGE_DIR%\\scripts\\_wlan_pdf_deps"
if exist "%WLAN_VENDOR_DEPS%\\pypdf" (
  if defined PYTHONPATH (set "PYTHONPATH=%WLAN_VENDOR_DEPS%;%PYTHONPATH%") else (set "PYTHONPATH=%WLAN_VENDOR_DEPS%")
)

echo {config["title"]}
echo Source: %SOURCE_DIR%
echo Glob: %GLOB%
echo Runtime: %PACKAGE_DIR%
echo Output: %COMBINED_OUTPUT_XLSX%
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

call :run_feature "Storage" "%STORAGE_SCRIPT_NAME%" "{config["storage_runtime_text"]}" "{config["storage_generated_text"]}" "%STORAGE_OUTPUT_XLSX%"
if errorlevel 1 goto :finish
{display["run_feature"]}call :run_feature "WLAN" "%WLAN_SCRIPT_NAME%" "{config["wlan_runtime_text"]}" "{config["wlan_generated_text"]}" "%WLAN_OUTPUT_XLSX%"
if errorlevel 1 goto :finish

call :merge_features
if errorlevel 1 goto :finish

set "EXIT_CODE=0"

if "%EXIT_CODE%"=="0" (
  if exist "%TEMP_OUTPUT_DIR%" rmdir /s /q "%TEMP_OUTPUT_DIR%" >nul 2>nul
  if exist "%OUTPUT_DIR%\\analysis_output" rmdir "%OUTPUT_DIR%\\analysis_output" >nul 2>nul
)

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
  echo Output: %COMBINED_OUTPUT_XLSX%
) else (
  echo Failed with exit code %EXIT_CODE%.
  echo Temp output folder: %TEMP_OUTPUT_DIR%
)
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%

:run_feature
set "FEATURE_NAME=%~1"
set "FEATURE_SCRIPT=%~2"
set "FEATURE_RUNTIME_TEXT=%~3"
set "FEATURE_GENERATED_TEXT=%~4"
set "FEATURE_OUTPUT=%~5"
set "FEATURE_EXIT_CODE=1"
set "FEATURE_RUNTIME_TEXT_DIR=%SOURCE_DIR%\\analysis_output\\%FEATURE_RUNTIME_TEXT%"
set "FEATURE_GENERATED_TEXT_DIR=%SOURCE_DIR%\\analysis_output\\%FEATURE_GENERATED_TEXT%"

echo.
echo Starting %FEATURE_NAME% generator...
pushd "%PACKAGE_DIR%\\scripts"
"%PYTHON_EXE%" ".\\%FEATURE_SCRIPT%" --spec-dir "%SOURCE_DIR%" --glob "%GLOB%" --output-xlsx "%FEATURE_OUTPUT%" --workbook-layout "%WORKBOOK_LAYOUT%" --runtime-text-dir "%FEATURE_RUNTIME_TEXT_DIR%" --generated-text-dir "%FEATURE_GENERATED_TEXT_DIR%"
set "FEATURE_EXIT_CODE=%ERRORLEVEL%"
popd

if not "%FEATURE_EXIT_CODE%"=="0" (
  set "EXIT_CODE=%FEATURE_EXIT_CODE%"
  echo ERROR: %FEATURE_NAME% generator failed with exit code %FEATURE_EXIT_CODE%.
  exit /b %FEATURE_EXIT_CODE%
)

echo Completed %FEATURE_NAME% generator.
exit /b 0

:merge_features
set "MERGE_EXIT_CODE=1"
echo.
echo Merging feature workbooks...
pushd "%PACKAGE_DIR%\\scripts"
"%PYTHON_EXE%" ".\\%MERGE_SCRIPT_NAME%" --output-xlsx "%COMBINED_OUTPUT_XLSX%" --feature "Storage" "%STORAGE_OUTPUT_XLSX%"{display["merge_arg"]} --feature "WLAN" "%WLAN_OUTPUT_XLSX%"
set "MERGE_EXIT_CODE=%ERRORLEVEL%"
popd

if not "%MERGE_EXIT_CODE%"=="0" (
  set "EXIT_CODE=%MERGE_EXIT_CODE%"
  echo ERROR: Workbook merge failed with exit code %MERGE_EXIT_CODE%.
  exit /b %MERGE_EXIT_CODE%
)

echo Completed workbook merge.
exit /b 0
"""


def release_dir_for_today(repo_root: Path) -> Path:
    return repo_root / "release" / f"sdw_{datetime.now():%y%m%d}"


def find_runtime_source(repo_root: Path, target_runtime: Path) -> Path | None:
    candidates = [repo_root / "rt", repo_root / "shortspec_portable_clean", target_runtime]
    release_root = repo_root / "release"
    if release_root.exists():
        for pattern in (
            "sdw_*",
            "storage_display_wifi_short_spec_generator_*",
            "storage_short_spec_generator_*",
            "display_short_spec_generator_*",
            "wlan_short_spec_generator_*",
            "short_spec_generator_*",
        ):
            for release_dir in sorted(release_root.glob(pattern), reverse=True):
                candidates.append(release_dir / "rt")
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


def sync_pdf_deps(repo_root: Path, target_runtime: Path) -> None:
    for feature in ("storage", "display", "wlan"):
        target_vendor = target_runtime / "scripts" / f"_{feature}_pdf_deps"
        safe_rmtree(target_vendor, target_runtime)

        for candidate in (repo_root / "analysis_output" / "pdf_deps", repo_root / "pdf_deps"):
            if (candidate / "pypdf").exists():
                shutil.copytree(candidate, target_vendor, ignore=ignore_generated_files)
                break


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
        shutil.copytree(source, target, ignore=ignore_generated_files)

    sync_pdf_deps(repo_root, target_runtime)


def write_release_readme(target_dir: Path) -> None:
    (target_dir / "README_sdw.txt").write_text(
        "\r\n".join(
            [
                "Storage + Display + Wi-Fi ShortSpec Generator portable release.",
                "",
                "Copy this whole folder to another PC, then put full spec PDFs next to the required .bat launcher.",
                "Run the matching .bat file. It generates one combined workbook next to the launcher by default.",
                "",
                "Delivered launchers and default output workbooks:",
                "- sdw_com.bat -> sdw_com.xlsx: commercial laptops, Storage + Display + Wi-Fi",
                "- sdw_con.bat -> sdw_con.xlsx: consumer laptops, Storage + Display + Wi-Fi",
                "- sdw_smb.bat -> sdw_smb.xlsx: SMB laptops, Storage + Display + Wi-Fi",
                "- sdw_tab.bat -> sdw_tab.xlsx: tablets, Storage + Display + Wi-Fi",
                "- sdw_dt.bat -> sdw_dt.xlsx: desktops, Storage + Display + Wi-Fi",
                "- sw_ts.bat -> sw_ts.xlsx: ThinkStation, Storage + Wi-Fi only",
                "",
                "The rt folder is required and must stay next to the launchers.",
                "The launcher deletes processed source PDFs only after all enabled generators and the workbook merge complete successfully.",
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

    generated_workbooks = {config["combined_output"] for config in COMBINED_LAUNCHERS}
    generated_outputs = set(generated_workbooks)
    generated_outputs.update(Path(name).with_suffix(".json").name for name in generated_workbooks)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in target_dir.rglob("*"):
            if path.is_dir():
                continue
            relative = path.relative_to(target_dir)
            if path.name.startswith("~$"):
                continue
            if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if relative.parts and relative.parts[0] == "analysis_output":
                continue
            if len(relative.parts) == 1 and path.name in generated_outputs:
                continue
            archive.write(path, Path(target_dir.name, relative).as_posix())

    return zip_path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    release_root = repo_root / "release"
    target_dir = release_dir_for_today(repo_root)
    release_root.mkdir(parents=True, exist_ok=True)
    safe_rmtree(target_dir, release_root)
    target_dir.mkdir(parents=True, exist_ok=True)

    sync_runtime(repo_root, target_dir / "rt")
    write_release_readme(target_dir)
    (target_dir / ".sdw_package").write_text(
        "folder_portable_storage_display_wifi\n",
        encoding="utf-8",
    )

    for config in COMBINED_LAUNCHERS:
        content = build_launcher(config)
        target = target_dir / config["release_bat"]
        target.write_text(content, encoding="utf-8", newline="\r\n")
        print(target)

    print(zip_release(target_dir))


if __name__ == "__main__":
    main()
