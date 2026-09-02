from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path

from build_sdw_html_validation_launchers import safe_rmtree, sync_runtime


OSKC_LAUNCHERS = [
    ("h_mkosc_com.bat", "com", "Lenovo Commercial Laptop HTML Memory/Keyboard/OS/Special/Cert ShortSpec", "h_mkosc_com.xlsx"),
    ("h_mkosc_con.bat", "con", "Lenovo Consumer Laptop HTML Memory/Keyboard/OS/Special/Cert ShortSpec", "h_mkosc_con.xlsx"),
    ("h_mkosc_smb.bat", "smb", "Lenovo SMB Laptop HTML Memory/Keyboard/OS/Special/Cert ShortSpec", "h_mkosc_smb.xlsx"),
    ("h_mkosc_tab.bat", "tab", "Lenovo Tablet HTML Memory/Keyboard/OS/Special/Cert ShortSpec", "h_mkosc_tab.xlsx"),
    ("h_mkosc_dt.bat", "dt", "Lenovo Desktop HTML Memory/OS/Special/Cert ShortSpec", "h_mkosc_dt.xlsx"),
    ("h_mkosc_ts.bat", "ts", "Lenovo ThinkStation HTML Memory/OS/Special/Cert ShortSpec", "h_mkosc_ts.xlsx"),
]


def release_dir_for_today(repo_root: Path) -> Path:
    return repo_root / "release" / f"mkosc_html_{datetime.now():%y%m%d}"


def build_launcher(config_key: str, title: str, output_name: str) -> str:
    scope = (
        "Operating System, Special Features, Memory, and Other Certifications"
        if config_key in {"dt", "ts"}
        else "Operating System, Special Features, Memory, Keyboard, and Other Certifications"
    )
    return f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM {title} - HTML source launcher
REM Default behavior:
REM   - process *.html from the same folder as this launcher
REM   - generate one workbook with only {scope}
REM   - delete source HTML files from this launcher folder after successful generation
REM   - keep manifests and process files under _work
REM   - no local Python installation required
REM   - requires rt next to this launcher or one level above
REM ============================================================

set "LAUNCHER_DIR=%~dp0"
for %%I in ("%LAUNCHER_DIR%\\.") do set "LAUNCHER_ROOT=%%~fI"
if not defined SOURCE_DIR set "SOURCE_DIR=%LAUNCHER_DIR%"
if not defined OUTPUT_DIR set "OUTPUT_DIR=%LAUNCHER_DIR%"
if not defined WORK_DIR set "WORK_DIR=%LAUNCHER_DIR%_work"
if not defined GLOB set "GLOB=*.html"
if not defined WORKBOOK_LAYOUT set "WORKBOOK_LAYOUT=single_sheet_summary"
for %%I in ("%SOURCE_DIR%\\.") do set "SOURCE_DIR=%%~fI"
for %%I in ("%OUTPUT_DIR%\\.") do set "OUTPUT_DIR=%%~fI"
for %%I in ("%WORK_DIR%\\.") do set "WORK_DIR=%%~fI"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%"
if not defined OUTPUT_XLSX set "OUTPUT_XLSX=%OUTPUT_DIR%\\{output_name}"

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
if not exist "%PACKAGE_DIR%\\scripts\\html_oskc_runner.py" (
  echo ERROR: Missing HTML OS/Special/Memory/Keyboard/Cert runner:
  echo %PACKAGE_DIR%\\scripts\\html_oskc_runner.py
  goto :finish
)

set "PYTHON_EXE=%PACKAGE_DIR%\\python-runtime\\python.exe"
set "PYTHONUTF8=1"

echo {title}
echo Source: %SOURCE_DIR%
echo Glob: %GLOB%
echo Runtime: %PACKAGE_DIR%
echo Output: %OUTPUT_XLSX%
echo Work: %WORK_DIR%
echo.

pushd "%PACKAGE_DIR%\\scripts"
"%PYTHON_EXE%" ".\\html_oskc_runner.py" --config "{config_key}" --source-dir "%SOURCE_DIR%" --glob "%GLOB%" --output-xlsx "%OUTPUT_XLSX%" --work-dir "%WORK_DIR%" --workbook-layout "%WORKBOOK_LAYOUT%"
set "EXIT_CODE=%ERRORLEVEL%"
popd

:finish
echo.
if "%EXIT_CODE%"=="0" (
  echo Completed successfully.
  echo Output: %OUTPUT_XLSX%
  if /I "%SOURCE_DIR%"=="%LAUNCHER_ROOT%" (
    set "DELETED_HTML=0"
    for %%F in ("%SOURCE_DIR%\\%GLOB%") do (
      if exist "%%~fF" (
        if /I "%%~xF"==".html" (
          del /q "%%~fF"
          set /a DELETED_HTML+=1
        ) else if /I "%%~xF"==".htm" (
          del /q "%%~fF"
          set /a DELETED_HTML+=1
        )
      )
    )
    if not "!DELETED_HTML!"=="0" echo Deleted source HTML files: !DELETED_HTML!
  )
) else (
  echo Failed with exit code %EXIT_CODE%.
)
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
"""


def write_release_readme(target_dir: Path) -> None:
    docs_dir = target_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "README_html_mkosc.txt").write_text(
        "\r\n".join(
            [
                "HTML-source Memory/Keyboard/OS/Special/Cert ShortSpec generator.",
                "",
                "Output scope:",
                "- Operating System",
                "- Special Features",
                "- Memory",
                "- Keyboard (Commercial, Consumer, SMB, and Tablet only; omitted for DT and ThinkStation)",
                "- Other Certifications",
                "",
                "Output columns:",
                "- Product",
                "- L1 Feature",
                "- L2 Feature",
                "- Short Spec",
                "- Note",
                "",
                "Note column:",
                "- Note is the shared field for feature-level notes.",
                "- Current Memory Type notes are written to Note and are not appended to the Memory Short Spec cell.",
                "- Future feature notes should also use this column.",
                "",
                "Rule sources:",
                "- Operating System and Special Features: latest product-line full rule-based rules using HTML-converted source text.",
                "- Memory: HTML Max Memory, Memory Slots, and Memory Type rules. ThinkStation uses Max Memory directly. Soldered output ends with not upgradable. Memory Type notes are written to the shared Note column.",
                "- Keyboard: HTML Keyboard and Keyboard Backlight feature override. Commercial, Consumer, SMB, and Tablet extract row count, multimedia Fn keys, spill-resistant, numeric keypad, and Chrome keyboard when present; DT and ThinkStation omit Keyboard.",
                "- If multiple positive Keyboard options produce the same extracted value, each option outputs that extracted value followed by that option's differing non-common parts with original wording.",
                "- Keyboard ignores None/No options, adds * to all remaining output options when an ignored option exists, removes model prefixes and parenthesized text, and joins multiple positive Keyboard Backlight values with \" / \". Only the last Backlight value keeps the word backlight.",
                "- Other Certifications for non-ThinkStation products: values from all HTML feature blocks tagged div specstructure=\"Other Certifications\", one option per line.",
                "- Other Certifications feature values are output before Mil-Spec Test values, source option order is preserved within each group, and registered/trademark symbols are removed.",
                "- Mil-Spec Test value Work in progress is ignored.",
                "- Other Certifications is omitted when the HTML does not contain div specstructure=\"Other Certifications\". ThinkStation omits Other Certifications.",
                "",
                "Default source folder: package root, next to the launchers.",
                "Default source pattern: *.html",
                "Default output: one workbook next to the launcher.",
                "Source HTML files in the package root are deleted after successful generation.",
                "Process files and manifests: _work",
                "",
                "Launchers:",
                "- h_mkosc_com.bat -> h_mkosc_com.xlsx: commercial laptops",
                "- h_mkosc_con.bat -> h_mkosc_con.xlsx: consumer laptops",
                "- h_mkosc_smb.bat -> h_mkosc_smb.xlsx: SMB laptops",
                "- h_mkosc_tab.bat -> h_mkosc_tab.xlsx: tablets",
                "- h_mkosc_dt.bat -> h_mkosc_dt.xlsx: desktops",
                "- h_mkosc_ts.bat -> h_mkosc_ts.xlsx: ThinkStation",
                "",
                "Set SOURCE_DIR to run against HTML files in another folder.",
                "Set GLOB if the HTML file name does not match *.html.",
                "The rt folder is required and must stay next to the launchers.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\r\n",
    )


def zip_release(target_dir: Path) -> Path:
    zip_path = target_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()

    generated_workbooks = {output_name for _, _, _, output_name in OSKC_LAUNCHERS}
    generated_outputs = set(generated_workbooks)
    generated_outputs.update(Path(name).with_suffix(".json").name for name in generated_workbooks)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in target_dir.rglob("*"):
            relative = path.relative_to(target_dir)
            if path.is_dir():
                if relative.parts and relative.parts[0] in {"_work", "analysis_output"}:
                    continue
                if "__pycache__" in relative.parts:
                    continue
                archive.writestr(Path(target_dir.name, relative).as_posix().rstrip("/") + "/", b"")
                continue
            if path.name.startswith("~$"):
                continue
            if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if relative.parts and relative.parts[0] in {"analysis_output", "_work"}:
                continue
            if len(relative.parts) == 1 and path.name in generated_outputs:
                continue
            if re.match(r"h_(?:mkosc|oskc)_.*\.(xlsx|json)$", path.name):
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
    meta_dir = target_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "html_mkosc_package.txt").write_text(
        "folder_portable_html_memory_keyboard_os_special_cert_shortspec\n",
        encoding="utf-8",
    )

    for bat_name, config_key, title, output_name in OSKC_LAUNCHERS:
        target = target_dir / bat_name
        target.write_text(build_launcher(config_key, title, output_name), encoding="utf-8", newline="\r\n")
        print(target)

    print(zip_release(target_dir))


if __name__ == "__main__":
    main()
