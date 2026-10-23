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
        if self.h3_depth:
            value = " ".join(data.split())
            if value:
                self.h3_parts.append(value)
        if self.value_depth:
            name = " ".join(" ".join(self.h3_parts).split()) or self.feature_name
            if feature_key(name) == "material":
                for line in data.splitlines():
                    value = " ".join(line.split())
                    if value:
                        self.value_parts.append(value)
                        self._flush_value()
            else:
                value = " ".join(data.split())
                if value:
                    self.value_parts.append(value)


def feature_values(html_text: str) -> dict[str, list[str]]:
    parser = FeatureValueParser()
    parser.feed(html_text)
    parser.close()
    result: dict[str, list[str]] = {}
    for name, values in parser.features:
        result.setdefault(feature_key(name), []).extend(plain_text(value) for value in values if plain_text(value))
    if parser.features:
        return result
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


def feature_groups_for_structure(html_text: str, structure_name: str) -> list[tuple[str, list[str]]]:
    """Return ordered h3/value groups under one matching h2 specStructure section."""
    headings = list(re.finditer(r"<h[12]\b[^>]*>.*?</h[12]>", html_text, flags=re.I | re.S))
    target = feature_key(structure_name)
    for index, heading in enumerate(headings):
        opening = re.match(r"<h2\b([^>]*)>", heading.group(), flags=re.I)
        if not opening:
            continue
        attrs = opening.group(1)
        structure = re.search(r"\bspecstructure\s*=\s*(['\"])(.*?)\1", attrs, flags=re.I | re.S)
        if not structure or feature_key(structure.group(2)) != target:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(html_text)
        parser = FeatureValueParser()
        parser.feed(html_text[heading.end():end])
        parser.close()
        return parser.features
    return []


def values_for(features: dict[str, list[str]], name: str) -> list[str]:
    return features.get(feature_key(name), [])


class FeatureTableParser(HTMLParser):
    """Extract header-addressable rows from tables inside one HTML Spec feature."""

    def __init__(self, feature_name: str, preserve_linebreaks: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.target = feature_key(feature_name)
        self.preserve_linebreaks = preserve_linebreaks
        self.feature_depth = 0
        self.table_depth = 0
        self.row: list[tuple[str, bool]] | None = None
        self.rows: list[list[tuple[str, bool]]] = []
        self.cell_depth = 0
        self.cell_parts: list[str] = []
        self.cell_is_header = False
        self.suptext_depth = 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = attr_map(attrs_list)
        if not self.feature_depth:
            if tag == "div" and attrs.get("specstructure") and feature_key(attrs["specstructure"]) == self.target:
                self.feature_depth = 1
            return
        self.feature_depth += 1
        if self.table_depth:
            self.table_depth += 1
        elif tag == "table":
            self.table_depth = 1
        if self.table_depth and tag == "tr":
            self.row = []
        if self.table_depth and tag in {"td", "th"} and self.row is not None:
            self.cell_depth = 1
            self.cell_parts = []
            self.cell_is_header = tag == "th" or "attr-header" in class_tokens(attrs)
        elif self.cell_depth:
            self.cell_depth += 1
        if self.suptext_depth:
            self.suptext_depth += 1
        elif tag == "span" and "supText" in class_tokens(attrs):
            self.suptext_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if not self.feature_depth:
            return
        tag = tag.lower()
        if self.suptext_depth:
            self.suptext_depth -= 1
        if self.cell_depth:
            self.cell_depth -= 1
            if self.cell_depth == 0 and self.row is not None:
                raw_value = " ".join(self.cell_parts)
                value = (
                    "\n".join(" ".join(line.split()) for line in raw_value.splitlines()).strip()
                    if self.preserve_linebreaks
                    else " ".join(raw_value.split())
                )
                self.row.append((value, self.cell_is_header))
        if self.table_depth and tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if self.table_depth:
            self.table_depth -= 1
        self.feature_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.cell_depth and not self.suptext_depth:
            value = data.replace("\r\n", "\n").replace("\r", "\n") if self.preserve_linebreaks else " ".join(data.split())
            if value:
                self.cell_parts.append(value)


def feature_table_rows(html_text: str, feature_name: str, preserve_linebreaks: bool = False) -> list[dict[str, str]]:
    """Return table rows keyed by their HTML Spec header labels, in source order."""
    parser = FeatureTableParser(feature_name, preserve_linebreaks=preserve_linebreaks)
    parser.feed(html_text)
    parser.close()
    for index, row in enumerate(parser.rows):
        if row and all(is_header for _, is_header in row):
            headers = [feature_key(value) for value, _ in row]
            result: list[dict[str, str]] = []
            for values in parser.rows[index + 1:]:
                if len(values) < len(headers) or all(is_header for _, is_header in values):
                    continue
                result.append({headers[column]: values[column][0] for column in range(len(headers))})
            return result
    return []


def feature_table_rows_for_heading(html_text: str, feature_name: str, preserve_linebreaks: bool = False) -> list[dict[str, str]]:
    """Return the first table directly associated with a matching h3 feature heading."""
    target = feature_key(feature_name)
    for match in re.finditer(r"<h3\b[^>]*>(.*?)</h3>", html_text, flags=re.I | re.S):
        if feature_key(match.group(1)) != target:
            continue
        section = html_text[match.end():]
        next_heading = re.search(r"<h[1-3]\b", section, flags=re.I)
        if next_heading:
            section = section[:next_heading.start()]
        table = re.search(r"<table\b[^>]*>.*?</table>", section, flags=re.I | re.S)
        if not table:
            return []
        fragment = f'<div specstructure="{feature_name}">{table.group(0)}</div>'
        return feature_table_rows(fragment, feature_name, preserve_linebreaks=preserve_linebreaks)
    return []


def feature_values_for_heading_preserving_lines(html_text: str, feature_name: str) -> list[str]:
    """Read a non-table feature value while retaining line breaks in its HTML text."""
    target = feature_key(feature_name)
    for match in re.finditer(
        r"<h3\b[^>]*>(.*?)</h3>\s*<div\b[^>]*class=['\"][^'\"]*divFeatureValue[^'\"]*['\"][^>]*>(.*?)</div>",
        html_text,
        flags=re.I | re.S,
    ):
        heading_html, value_html = match.groups()
        if feature_key(heading_html) != target or re.search(r"<table\b", value_html, flags=re.I):
            continue
        value_html = re.sub(r"<sup\b.*?</sup>", "", value_html, flags=re.I | re.S)
        value_html = re.sub(r"<br\b[^>]*>", "\n", value_html, flags=re.I)
        value_html = re.sub(r"</(?:li|p)\s*>", "\n", value_html, flags=re.I)
        text = html.unescape(re.sub(r"<[^>]+>", "", value_html)).replace("\xa0", " ")
        lines = [" ".join(line.split()) for line in text.splitlines()]
        value = "\n".join(line for line in lines if line)
        return [value] if "\n" in value else []
    return []


def remove_parentheses(value: str) -> str:
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\([^()]*\)", "", value)
    return " ".join(value.replace(" ,", ",").split()).strip(" ,;")


def positive_values(values: list[str]) -> tuple[list[str], bool]:
    no_present = any(value.lstrip().casefold().startswith("no") for value in values)
    return ([value for value in values if not value.lstrip().casefold().startswith("no")], no_present)


def camera_short_spec(values: list[str], product_line: str) -> str:
    """Render Camera entries according to the HTML product-line rules."""
    if not values:
        return ""
    has_no = any(value.lstrip().casefold().startswith("no") for value in values)
    if product_line == "tablet":
        return "\n".join(value + "*" if has_no and not value.endswith("*") else value for value in values)

    positive = [value for value in values if not value.lstrip().casefold().startswith("no")]
    rendered: list[str] = []
    for value in positive:
        first, separator, rest = value.partition(",")
        first = first.strip()
        if product_line == "desktop":
            detail = " RGB & IR hybrid" if re.search(r"\bIR\b", rest, re.I) else " RGB"
            if "human presence detection" in rest.casefold():
                detail += " with Human Presence Detection"
            rendered.append(first + detail)
            continue

        parts = [first]
        if separator:
            keywords = ("human presence detection", "temporal noise reduction", "privacy shutter", "thinkshutter", "computer vision")
            segments = [segment.strip() for segment in re.split(r"[,;]", rest)]
            for segment in segments:
                if any(keyword in segment.casefold() for keyword in keywords):
                    parts.append(segment)
            for segment in segments:
                if not re.match(r"rear\b", segment, re.I):
                    continue
                rear = re.sub(r"\bworld facing\b", "", segment, flags=re.I)
                rear = " ".join(rear.split()).strip()
                if rear:
                    parts.append(rear)
        rendered.append(", ".join(parts))

    distinct = unique_values(rendered)
    return "\n".join(value + "*" if has_no and not value.endswith("*") else value for value in distinct)


def audio_chip_term(value: str, multiple_conditions: bool) -> str | None:
    """Keep an Audio Chip branch label when the feature has multiple branches."""
    match = re.search(r"SoundWire|High Definition \(HD\) Audio", value, flags=re.I)
    if not match:
        return None
    if multiple_conditions:
        condition = re.match(r"\s*([^:]+):\s*", value)
        if condition and condition.end() <= match.start():
            return f"{condition.group(1).strip()}: {match.group(0)}"
    return match.group(0)


def audio_has_multiple_conditions(values: list[str]) -> bool:
    return sum(bool(re.match(r"\s*[^:]+:\s*", value)) for value in values) > 1


def non_tablet_battery_life(values: list[str]) -> str:
    """Select the largest MobileMark version, then its longest stated runtime."""
    mobilemark = re.compile(r"\bMobileMark\s*[®™]?\s*(\d+(?:\.\d+)?)?", re.I)
    hours = re.compile(r"(\d+(?:\.\d+)?)\s*hr\b", re.I)
    candidates: list[tuple[float, float]] = []
    has_mobilemark = False
    for value in values:
        matches = list(mobilemark.finditer(value))
        has_mobilemark |= bool(matches)
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
            runtime = hours.search(value, match.end(), end)
            if runtime:
                version = float(match.group(1)) if match.group(1) else float("-inf")
                candidates.append((version, float(runtime.group(1))))
    if candidates:
        return f"Up to {max(candidates)[1]:g} hr"
    if has_mobilemark:
        return ""
    runtimes = [float(match.group(1)) for value in values for match in hours.finditer(value)]
    return f"Up to {max(runtimes):g} hr" if runtimes else ""


def finalize_short_spec(value: str) -> str:
    """Apply output-wide ShortSpec cleanup immediately before workbook writing."""
    value = re.sub(
        r"<span\b(?=[^>]*\bclass\s*=\s*['\"][^'\"]*\bsupText\b[^'\"]*['\"])[^>]*>.*?</span>",
        "",
        value,
        flags=re.I | re.S,
    )
    value = html.unescape(value)
    return re.sub(r"\.(?=[ \t]*(?:\r?\n|$))", "", value)


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
