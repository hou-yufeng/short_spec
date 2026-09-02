from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from build_sdw_html_validation_launchers import ensure_inside, safe_rmtree, sync_runtime


HTML_ALL_LAUNCHERS = [
    ("h_all_com.bat", "com", "Lenovo Commercial Laptop HTML Full ShortSpec", "h_all_com.xlsx"),
    ("h_all_con.bat", "con", "Lenovo Consumer Laptop HTML Full ShortSpec", "h_all_con.xlsx"),
    ("h_all_smb.bat", "smb", "Lenovo SMB Laptop HTML Full ShortSpec", "h_all_smb.xlsx"),
    ("h_all_tab.bat", "tab", "Lenovo Tablet HTML Full ShortSpec", "h_all_tab.xlsx"),
    ("h_all_dt.bat", "dt", "Lenovo Desktop HTML Full ShortSpec", "h_all_dt.xlsx"),
    ("h_all_ts.bat", "ts", "Lenovo ThinkStation HTML Full ShortSpec", "h_all_ts.xlsx"),
]


def release_dir_for_today(repo_root: Path) -> Path:
    return repo_root / "release" / f"all_html_{datetime.now():%y%m%d}"


def build_launcher(config_key: str, title: str, output_name: str) -> str:
    return f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM {title} - HTML source launcher
REM Default behavior:
REM   - process *.html from the same folder as this launcher
REM   - generate one full ShortSpec workbook next to this launcher
REM   - Storage, Display, and WLAN use latest HTML SDW rules
REM   - all other features use latest PDF full rule-based rules
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
if not exist "%PACKAGE_DIR%\\scripts\\html_all_runner.py" (
  echo ERROR: Missing HTML full runner:
  echo %PACKAGE_DIR%\\scripts\\html_all_runner.py
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
"%PYTHON_EXE%" ".\\html_all_runner.py" --config "{config_key}" --source-dir "%SOURCE_DIR%" --glob "%GLOB%" --output-xlsx "%OUTPUT_XLSX%" --work-dir "%WORK_DIR%" --workbook-layout "%WORKBOOK_LAYOUT%"
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
    (docs_dir / "README_html_all.txt").write_text(
        "\r\n".join(
            [
                "HTML-source full ShortSpec generator.",
                "",
                "Rule sources:",
                "- Storage, Display, and WLAN: latest HTML SDW deliverable rules.",
                "- WLAN: before existing WLAN selection, HTML WLAN options with identical first two comma-separated segments are treated as one WLAN option.",
                "- All other features: latest PDF full ShortSpec deliverable rules.",
                "",
                "Default source folder: package root, next to the launchers.",
                "Default source pattern: *.html",
                "Default output: one full ShortSpec workbook next to the launcher.",
                "Source HTML files in the package root are deleted after successful generation.",
                "Process files and manifests: _work",
                "",
                "Launchers:",
                "- h_all_com.bat -> h_all_com.xlsx: commercial laptops",
                "- h_all_con.bat -> h_all_con.xlsx: consumer laptops",
                "- h_all_smb.bat -> h_all_smb.xlsx: SMB laptops",
                "- h_all_tab.bat -> h_all_tab.xlsx: tablets",
                "- h_all_dt.bat -> h_all_dt.xlsx: desktops",
                "- h_all_ts.bat -> h_all_ts.xlsx: ThinkStation",
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
    ensure_inside(zip_path, target_dir.parent)
    if zip_path.exists():
        zip_path.unlink()

    generated_workbooks = {output_name for _, _, _, output_name in HTML_ALL_LAUNCHERS}
    generated_outputs = set(generated_workbooks)
    generated_outputs.update(Path(name).with_suffix(".json").name for name in generated_workbooks)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in target_dir.rglob("*"):
            relative = path.relative_to(target_dir)
            if path.is_dir():
                if relative.parts and relative.parts[0] == "_work":
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
    (meta_dir / "html_all_package.txt").write_text(
        "folder_portable_full_shortspec_html_source\n",
        encoding="utf-8",
    )

    for bat_name, config_key, title, output_name in HTML_ALL_LAUNCHERS:
        target = target_dir / bat_name
        target.write_text(build_launcher(config_key, title, output_name), encoding="utf-8", newline="\r\n")
        print(target)

    print(zip_release(target_dir))


if __name__ == "__main__":
    main()
