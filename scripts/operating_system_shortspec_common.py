from __future__ import annotations

import re
from collections.abc import Iterable


def _clean_value(value: str) -> str:
    value = re.sub(r"\[[0-9,\s]+\]", "", value)
    value = value.replace("\u2022", "")
    value = re.sub(r"\*+$", "", value)
    value = re.sub(r"\bSingle Language\b", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return value


def _is_skipped_value(value: str) -> bool:
    lowered = value.lower().strip()
    if not lowered:
        return True
    if lowered in {"operating system", "operating system feature"}:
        return True
    if lowered.startswith(("no preload", "no operating system")):
        return True
    if lowered.startswith("red hat certified hardware"):
        return True
    if "license can be requested" in lowered or "some features may not be supported" in lowered:
        return True
    return False


def _unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def normalize_operating_system_values(values: Iterable[str]) -> list[str]:
    raw_values = [str(raw_value) for raw_value in values]
    has_arm_option = any(re.search(r"\(\s*on\s+ARM\s*\)", value, flags=re.I) for value in raw_values)
    normalized: list[str] = []
    for raw_value in raw_values:
        value = _clean_value(re.sub(r"\s*\(\s*on\s+ARM\s*\)", "", raw_value, flags=re.I))
        if _is_skipped_value(value):
            continue

        if re.search(r"\bRed Hat Enterprise Linux\b", value, flags=re.I):
            normalized.append("Red Hat Enterprise Linux (certified only)")
            continue

        normalized.append(value)

    normalized = _unique_preserve(normalized)
    has_windows_11_pro = any(re.search(r"\bWindows\s+11\s+Pro\b", value, flags=re.I) for value in normalized)
    has_windows_11_home = any(re.search(r"\bWindows\s+11\s+Home\b", value, flags=re.I) for value in normalized)
    has_fedora = any("fedora" in value.lower() for value in normalized)
    has_ubuntu = any("ubuntu" in value.lower() for value in normalized)
    has_named_linux_distro = has_fedora or has_ubuntu or any(
        "red hat enterprise linux" in value.lower() for value in normalized
    )

    output: list[str] = []
    added_windows_11 = False
    added_fedora_ubuntu = False

    for value in normalized:
        lowered = value.lower()

        if has_windows_11_pro and has_windows_11_home and re.search(r"\bWindows\s+11\s+(?:Pro|Home)\b", value, flags=re.I):
            if not added_windows_11:
                output.append("Windows 11 Pro or Home")
                added_windows_11 = True
            continue

        if has_fedora and has_ubuntu and ("fedora" in lowered or "ubuntu" in lowered):
            if not added_fedora_ubuntu:
                output.append("Fedora or Ubuntu Linux")
                added_fedora_ubuntu = True
            continue

        if lowered == "linux" and has_named_linux_distro:
            continue

        output.append(value)

    output = _unique_preserve(output)
    if has_arm_option and output:
        output[-1] = f"{output[-1]} (on ARM)"
    return output
