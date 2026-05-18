from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path


EXCLUDED_LIB_DIRS = {
    "__pycache__",
    "curses",
    "ensurepip",
    "idlelib",
    "site-packages",
    "test",
    "tkinter",
    "turtledemo",
    "venv",
}

EXCLUDED_LIB_SUFFIXES = {
    ".pickle",
    ".pyc",
    ".pyo",
    ".pyd",
    ".pdb",
}

EXCLUDED_DLL_NAMES = {
    "python_lib.cat",
    "py.ico",
    "pyc.ico",
    "pyd.ico",
    "tcl86t.dll",
    "tk86t.dll",
}


def current_free_threaded_markers() -> tuple[str, ...]:
    major = sys.version_info.major
    minor = sys.version_info.minor
    return (
        f"cp{major}{minor}t",
        f"python{major}{minor}t",
        f"python{major}t",
        f"python{major}.{minor}t",
    )


def should_include_lib_file(path: Path) -> bool:
    if path.is_dir():
        return False
    if any(part in EXCLUDED_LIB_DIRS for part in path.parts):
        return False
    if path.suffix.lower() in EXCLUDED_LIB_SUFFIXES:
        return False
    return True


def should_include_dll_file(path: Path) -> bool:
    name = path.name.lower()
    if not path.is_file():
        return False
    if name in EXCLUDED_DLL_NAMES:
        return False
    if path.suffix.lower() not in {".dll", ".pyd"}:
        return False
    if ".pdb" in name or ".lib" in name:
        return False
    if "_d." in name or name.endswith("_d.pyd") or name.endswith("_d.dll"):
        return False
    if any(marker in name for marker in current_free_threaded_markers()):
        return False
    return True


def build_portable_python_runtime() -> bytes:
    python_home = Path(sys.base_prefix).resolve()
    major = sys.version_info.major
    minor = sys.version_info.minor
    version_tag = f"python{major}{minor}"

    runtime_buffer = io.BytesIO()
    with zipfile.ZipFile(runtime_buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as runtime_zip:
        stdlib_buffer = io.BytesIO()
        lib_dir = python_home / "Lib"
        with zipfile.ZipFile(stdlib_buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stdlib_zip:
            for path in sorted(lib_dir.rglob("*")):
                rel = path.relative_to(lib_dir)
                if should_include_lib_file(rel):
                    stdlib_zip.write(path, rel.as_posix())

        runtime_zip.writestr(f"{version_tag}.zip", stdlib_buffer.getvalue())

        for root_name in (
            "LICENSE.txt",
            "python.exe",
            "python3.dll",
            f"{version_tag}.dll",
            "vcruntime140.dll",
            "vcruntime140_1.dll",
        ):
            source = python_home / root_name
            if not source.exists():
                raise FileNotFoundError(f"Portable Python build missing required runtime file: {source}")
            runtime_zip.write(source, source.name)

        dll_dir = python_home / "DLLs"
        for path in sorted(dll_dir.iterdir()):
            if should_include_dll_file(path):
                runtime_zip.write(path, f"DLLs/{path.name}")

    return runtime_buffer.getvalue()
