from __future__ import annotations

import io
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


HTML_LAUNCHERS = [
    ("h_sdw_com.bat", "com", "Lenovo Commercial Laptop HTML Storage Display Wi-Fi ShortSpec", "h_sdw_com.xlsx"),
    ("h_sdw_con.bat", "con", "Lenovo Consumer Laptop HTML Storage Display Wi-Fi ShortSpec", "h_sdw_con.xlsx"),
    ("h_sdw_smb.bat", "smb", "Lenovo SMB Laptop HTML Storage Display Wi-Fi ShortSpec", "h_sdw_smb.xlsx"),
    ("h_sdw_tab.bat", "tab", "Lenovo Tablet HTML Storage Display Wi-Fi ShortSpec", "h_sdw_tab.xlsx"),
    ("h_sdw_dt.bat", "dt", "Lenovo Desktop HTML Storage Display Wi-Fi ShortSpec", "h_sdw_dt.xlsx"),
    ("h_sw_ts.bat", "ts", "Lenovo ThinkStation HTML Storage Wi-Fi ShortSpec", "h_sw_ts.xlsx"),
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


def release_dir_for_today(repo_root: Path) -> Path:
    return repo_root / "release" / f"sdw_html_{datetime.now():%y%m%d}"


def find_runtime_source(repo_root: Path, target_runtime: Path) -> Path | None:
    candidates = [repo_root / "rt", repo_root / "shortspec_portable_clean", target_runtime]
    release_root = repo_root / "release"
    if release_root.exists():
        for pattern in (
            "sdw_html_*",
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


def build_launcher(config_key: str, title: str, output_name: str) -> str:
    return f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM {title} - HTML source launcher
REM Default behavior:
REM   - process *.html from the same folder as this launcher
REM   - convert HTML to temporary text specs
REM   - generate one combined workbook next to this launcher
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
if not defined COMBINED_OUTPUT_XLSX set "COMBINED_OUTPUT_XLSX=%OUTPUT_DIR%\\{output_name}"

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
if not exist "%PACKAGE_DIR%\\scripts\\html_sdw_runner.py" (
  echo ERROR: Missing HTML runner:
  echo %PACKAGE_DIR%\\scripts\\html_sdw_runner.py
  goto :finish
)

set "PYTHON_EXE=%PACKAGE_DIR%\\python-runtime\\python.exe"
set "PYTHONUTF8=1"

echo {title}
echo Source: %SOURCE_DIR%
echo Glob: %GLOB%
echo Runtime: %PACKAGE_DIR%
echo Output: %COMBINED_OUTPUT_XLSX%
echo Work: %WORK_DIR%
echo.

pushd "%PACKAGE_DIR%\\scripts"
"%PYTHON_EXE%" ".\\html_sdw_runner.py" --config "{config_key}" --source-dir "%SOURCE_DIR%" --glob "%GLOB%" --output-xlsx "%COMBINED_OUTPUT_XLSX%" --work-dir "%WORK_DIR%" --workbook-layout "%WORKBOOK_LAYOUT%"
set "EXIT_CODE=%ERRORLEVEL%"
popd

:finish
echo.
if "%EXIT_CODE%"=="0" (
  echo Completed successfully.
  echo Output: %COMBINED_OUTPUT_XLSX%
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
    (docs_dir / "README_html_sdw.txt").write_text(
        "\r\n".join(
            [
                "HTML-source branch for the Storage + Display + Wi-Fi ShortSpec integrated generator.",
                "",
                "This package does not change the existing PDF deliverable or feature rules.",
                "It converts source HTML files into temporary text specs, then runs the existing rule-based generators and merges the feature workbooks.",
                "",
                "Root folder rule: launcher .bat files and generated .xlsx workbooks should remain in the package root after a successful run.",
                "Default source folder: package root, next to the launchers.",
                "Default source pattern: *.html",
                "Default output: one combined workbook next to the launcher.",
                "Source HTML files in the package root are deleted after successful generation.",
                "Process files and manifests: _work",
                "",
                "Launchers:",
                "- h_sdw_com.bat -> h_sdw_com.xlsx: commercial laptops, Storage + Display + Wi-Fi",
                "- h_sdw_con.bat -> h_sdw_con.xlsx: consumer laptops, Storage + Display + Wi-Fi",
                "- h_sdw_smb.bat -> h_sdw_smb.xlsx: SMB laptops, Storage + Display + Wi-Fi",
                "- h_sdw_tab.bat -> h_sdw_tab.xlsx: tablets, Storage + Display + Wi-Fi",
                "- h_sdw_dt.bat -> h_sdw_dt.xlsx: desktops, Storage + Display + Wi-Fi",
                "- h_sw_ts.bat -> h_sw_ts.xlsx: ThinkStation, Storage + Wi-Fi only",
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

    generated_workbooks = {output_name for _, _, _, output_name in HTML_LAUNCHERS}
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
    (meta_dir / "sdw_html_package.txt").write_text(
        "folder_portable_storage_display_wifi_html_source\n",
        encoding="utf-8",
    )

    for bat_name, config_key, title, output_name in HTML_LAUNCHERS:
        target = target_dir / bat_name
        target.write_text(build_launcher(config_key, title, output_name), encoding="utf-8", newline="\r\n")
        print(target)

    print(zip_release(target_dir))


if __name__ == "__main__":
    main()
