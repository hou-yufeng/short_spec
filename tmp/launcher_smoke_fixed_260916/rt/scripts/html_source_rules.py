"""HTML-source extraction helpers with no ShortSpec business decisions."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

BLOCK_TAGS = {"br", "div", "li", "p", "table", "tbody", "td", "th", "tr", "ul"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "sup"}


def attr_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name.casefold(): value or "" for name, value in attrs}


def class_tokens(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


def has_display_none(attrs: dict[str, str]) -> bool:
    return "display:none" in attrs.get("style", "").replace(" ", "").casefold()


def plain_text(value: str) -> str:
    value = re.sub(r"<sup\b.*?</sup>", "", value, flags=re.I | re.S)
    value = re.sub(r"<span\s+class=['\"]supText['\"][^>]*>.*?</span>", "", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(" ".join(value.replace("\xa0", " ").split()))


def feature_key(value: str) -> str:
    value = plain_text(value)
    value = re.sub(r"\[[^\]]*\]", "", value)
    value = value.replace("®", "").replace("™", "")
    value = re.sub(r"[*]+", "", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


class FeatureValueParser(HTMLParser):
    """Collect h3/value pairs beneath div[specstructure] without interpreting them."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.feature_depth = 0
        self.feature_name = ""
        self.h3_depth = 0
        self.h3_parts: list[str] = []
        self.value_depth = 0
        self.value_parts: list[str] = []
        self.values: list[str] = []
        self.features: list[tuple[str, list[str]]] = []

    def _flush_value(self) -> None:
        value = " ".join(" ".join(self.value_parts).split())
        if value:
            self.values.append(value)
        self.value_parts = []

    def _finish_feature(self) -> None:
        self._flush_value()
        name = " ".join(" ".join(self.h3_parts).split()) or self.feature_name
        if name and self.values:
            self.features.append((name, self.values.copy()))
        self.feature_depth = self.h3_depth = self.value_depth = 0
        self.feature_name = ""
        self.h3_parts = []
        self.value_parts = []
        self.values = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        classes = class_tokens(attrs)
        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in SKIP_TAGS or has_display_none(attrs) or "as_note_type" in classes:
            self.skip_depth = 1
            return
        if tag == "div" and attrs.get("specstructure"):
            if self.feature_depth:
                self._finish_feature()
            self.feature_depth = 1
            self.feature_name = attrs["specstructure"]
            return
        if self.feature_depth:
            self.feature_depth += 1
        if tag == "h3" and self.feature_depth:
            self.h3_depth = 1
            self.h3_parts = []
            return
        if self.h3_depth:
            self.h3_depth += 1
        if tag == "div" and self.feature_depth and "divFeatureValue" in classes:
            self.value_depth = 1
            self.value_parts = []
            return
        if self.value_depth:
            if tag in BLOCK_TAGS:
                self._flush_value()
            self.value_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if self.h3_depth:
            self.h3_depth -= 1
        if self.value_depth:
            if tag in BLOCK_TAGS:
                self._flush_value()
            self.value_depth -= 1
        if self.feature_depth:
            self.feature_depth -= 1
            if self.feature_depth == 0:
                self._finish_feature()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = " ".join(data.split())
        if not value:
            return
        if self.h3_depth:
            self.h3_parts.append(value)
        if self.value_depth:
            self.value_parts.append(value)


def feature_values(html_text: str) -> dict[str, list[str]]:
    parser = FeatureValueParser()
    parser.feed(html_text)
    parser.close()
    result: dict[str, list[str]] = {}
    for name, values in parser.features:
        result.setdefault(feature_key(name), []).extend(plain_text(value) for value in values if plain_text(value))
    # Older consumer pages have no div[specstructure].  Their feature name is
    # carried by an l3_* anchor inside the h3 immediately preceding the value.
    for match in re.finditer(
        r"<h3\b[^>]*>(.*?)</h3>\s*<div\b[^>]*class=['\"][^'\"]*divFeatureValue[^'\"]*['\"][^>]*>(.*?)</div>",
        html_text,
        flags=re.I | re.S,
    ):
        heading_html, value_html = match.groups()
        heading = plain_text(heading_html)
        anchor = re.search(r"\bid=['\"]l3_([^'\"]+)", heading_html, flags=re.I)
        if not heading and anchor:
            token = anchor.group(1)
            special = {
                "OperatingSystem": "Operating System",
                "PowerAdapter": "Power Adapter",
                "StorageType": "Storage Type",
                "WLANBluetooth": "WLAN + Bluetooth",
                "BaseWarranty": "Base Warranty",
            }
            heading = special.get(token, re.sub(r"(?<!^)([A-Z])", r" \1", token))
        if not heading:
            continue
        list_items = re.findall(r"<li\b[^>]*>(.*?)</li>", value_html, flags=re.I | re.S)
        values = [plain_text(item) for item in list_items] if list_items else [plain_text(value_html)]
        values = [value for value in values if value]
        if values:
            result.setdefault(feature_key(heading), []).extend(values)
    return result


def values_for(features: dict[str, list[str]], name: str) -> list[str]:
    return features.get(feature_key(name), [])


def remove_parentheses(value: str) -> str:
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\([^()]*\)", "", value)
    return " ".join(value.replace(" ,", ",").split()).strip(" ,;")


def positive_values(values: list[str]) -> tuple[list[str], bool]:
    no_present = any(value.lstrip().casefold().startswith("no") for value in values)
    return ([value for value in values if not value.lstrip().casefold().startswith("no")], no_present)


def unique_values(values: list[str]) -> list[str]:
    """Preserve distinct non-empty values, comparing case-insensitively."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = " ".join(value.split()).strip(" ,;\n")
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    return result


def _touchpad_value(values: list[str]) -> str:
    primary: list[str] = []
    trailing: list[str] = []
    for value in values:
        value = re.sub(r"^\s*\d+\s*-\s*button\b\s*,?\s*", "", value, flags=re.I)
        value = re.sub(r"\bpointing device\b", "", value, flags=re.I)
        value = re.sub(r"\s*,?\s*double-tap to open the TrackPoint Quick Menu", "", value, flags=re.I)
        parts = [part.strip() for part in value.split(",")]
        value = ", ".join(part for part in parts if part and not part.casefold().startswith("supports"))
        value = re.sub(r"\s+,", ",", value).strip(" ,.")
        if not value:
            continue
        if "," in value:
            head, tail = value.rsplit(",", 1)
            primary.append(head.strip(" ,."))
            trailing.append(tail.strip(" ,."))
        else:
            primary.append(value)
    lines = [" or ".join(unique_values(primary))]
    if trailing:
        lines.append(" or ".join(unique_values(trailing)))
    return "\n".join(line for line in lines if line)


def additional_third_batch_values(features: dict[str, list[str]], product_line: str) -> list[tuple[str, str]]:
    """Return the five additive third-batch rules applicable to a product line."""
    result: list[tuple[str, str]] = []
    if product_line != "tablet":
        chipset = values_for(features, "Chipset")
        if chipset and not all("soc" in value.casefold() for value in chipset):
            result.append(("Chipset", "\n".join(unique_values(chipset))))
    if product_line == "consumer_laptop":
        controls = unique_values(values_for(features, "Controls"))
        if controls:
            result.append(("Controls", "\n".join(controls)))
    if product_line in {"commercial_laptop", "consumer_laptop", "smb_laptop"}:
        docking = values_for(features, "Docking")
        folio = "Chromebook folio keyboard with touchpad (Pogo pin, detachable)"
        no_keyboard = "No keyboard docking inbox"
        if any(value.casefold() == folio.casefold() for value in docking) and any(value.casefold() == no_keyboard.casefold() for value in docking):
            result.append(("Docking", folio + "*"))
        else:
            cleaned = []
            for value in docking:
                if value.casefold().startswith("for more compatible"):
                    continue
                value = re.sub(r"^Various docking", "Docking", value, flags=re.I)
                cleaned.append(value)
            cleaned = unique_values(cleaned)
            if cleaned:
                result.append(("Docking", "\n".join(cleaned)))
    if product_line in {"commercial_laptop", "consumer_laptop", "smb_laptop", "tablet"}:
        multi_mode = values_for(features, "Multi-mode")
        if multi_mode and not all(value.lstrip().casefold().startswith("no") for value in multi_mode):
            result.append(("Multi-mode", "\n".join(unique_values([value.split(":", 1)[0] for value in multi_mode]))))
    if product_line in {"commercial_laptop", "consumer_laptop", "smb_laptop"}:
        source = "UltraNav" if product_line == "commercial_laptop" else "Touchpad"
        touchpad = _touchpad_value(values_for(features, source))
        if touchpad:
            result.append(("Touchpad", touchpad))
    return result
