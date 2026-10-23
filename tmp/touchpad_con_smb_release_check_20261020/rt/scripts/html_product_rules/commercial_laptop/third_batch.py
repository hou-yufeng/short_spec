"""Commercial-laptop-owned HTML rules for the 33 third-batch features."""
from __future__ import annotations

import html
import re

from html_source_rules import audio_chip_term, audio_has_multiple_conditions, camera_short_spec, feature_table_rows, feature_table_rows_for_heading, feature_values_for_heading_preserving_lines, non_tablet_battery_life, positive_values, remove_parentheses, values_for

PRODUCT_LINE = "commercial_laptop"

L1 = {
    "Processor": "PERFORMANCE", "Graphics": "PERFORMANCE", "NPU": "PERFORMANCE", "AI PC Category": "PERFORMANCE", "Chipset": "PERFORMANCE",
    "Audio": "MULTIMEDIA", "Camera": "MULTIMEDIA", "Battery": "MOBILITY", "Charging Time": "MOBILITY",
    "Power Adapter": "MOBILITY", "Dimensions (WxDxH)": "DESIGN", "Weight": "DESIGN", "Color": "DESIGN",
    "Case Material": "DESIGN", "Material": "DESIGN", "Ports": "CONNECTIVITY", "Ethernet": "CONNECTIVITY",
    "WWAN": "CONNECTIVITY", "NFC": "CONNECTIVITY", "Pen": "DESIGN", "Security": "SECURITY & PRIVACY",
    "System Management": "MANAGEABILITY", "Base Warranty": "SERVICE", "Green Certifications": "CERTIFICATIONS",
    "ISV Certifications": "CERTIFICATIONS", "Screen-to-Body Ratio": "DESIGN",
}


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = " ".join(value.split()).strip(" ,;")
        if value and value.casefold() not in seen:
            seen.add(value.casefold()); out.append(value)
    return out


def _star(values: list[str], starred: bool) -> list[str]:
    return [value if not starred or value.endswith("*") else value + "*" for value in values]


def _security_values(features: dict[str, list[str]], name: str) -> tuple[list[str], bool]:
    values = values_for(features, name)
    has_no = any(re.match(r"\s*no\b", value, flags=re.I) for value in values)
    return [value for value in values if not re.match(r"\s*no\b", value, flags=re.I)], has_no


def _ai_pc_category(features: dict[str, list[str]]) -> str:
    values = values_for(features, "AI PC Category")
    has_no = any(value.lstrip().casefold().startswith("no") for value in values)
    return "\n".join(_star(_unique([value for value in values if not value.lstrip().casefold().startswith("no")]), has_no))

def _dimensions(features: dict[str, list[str]], html_text: str | None) -> list[str]:
    rows = feature_table_rows_for_heading(html_text, "Dimensions (WxDxH)", preserve_linebreaks=True) if html_text else []
    rows = [row for row in rows if row.get("dimensions")]
    if not rows:
        return (feature_values_for_heading_preserving_lines(html_text, "Dimensions (WxDxH)") if html_text else []) or values_for(features, "Dimensions (WxDxH)")
    if len(rows) == 1:
        return [rows[0]["dimensions"]]
    maximum_dimensions: list[tuple[float, str]] = []
    for row in rows:
        match = re.search(r"(\d+(?:\.\d+)?)\s*\(maximum\)\s*mm\b", row["dimensions"], flags=re.I)
        if match:
            maximum_dimensions.append((float(match.group(1)), row["dimensions"]))
    if maximum_dimensions:
        return [f"Starting at:\n{min(maximum_dimensions, key=lambda item: item[0])[1]}"]
    return [f"{row.get('models', '')}:\n{row['dimensions']}" for row in rows]


def _weight(features: dict[str, list[str]], html_text: str | None) -> list[str]:
    rows = feature_table_rows_for_heading(html_text, "Weight") if html_text else []
    rows = [row for row in rows if row.get("weight")]
    if not rows:
        return values_for(features, "Weight")
    if len(rows) == 1:
        return [rows[0]["weight"]]
    weights: list[tuple[float, str]] = []
    for row in rows:
        match = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", row["weight"], flags=re.I)
        if match:
            weights.append((float(match.group(1)), row["weight"]))
    if weights:
        return [min(weights, key=lambda item: item[0])[1]]
    return [row["weight"] for row in rows]


def _docking(features: dict[str, list[str]]) -> str:
    docking = values_for(features, "Docking")
    folio = "Chromebook folio keyboard with touchpad (Pogo pin, detachable)"
    no_keyboard = "No keyboard docking inbox"
    if any(value.casefold() == folio.casefold() for value in docking) and any(value.casefold() == no_keyboard.casefold() for value in docking):
        return folio + "*"
    cleaned: list[str] = []
    for value in docking:
        value = re.sub(r"\s*for more compatible.*$", "", value, flags=re.I).strip()
        if value:
            cleaned.append(re.sub(r"^Various docking", "Docking", value, flags=re.I))
    return "\n".join(_unique(cleaned))


def _graphics(features: dict[str, list[str]], html_text: str | None) -> list[str]:
    if not html_text:
        return []
    result: list[str] = []
    for row in feature_table_rows(html_text, "Graphics"):
        graphics = row.get("graphics", "").strip()
        graphics_type = row.get("type", "").strip().casefold()
        memory = row.get("memory", "").strip()
        if not graphics:
            continue
        if graphics_type == "discrete":
            if memory and "GB" not in graphics.upper() and memory.casefold() not in graphics.casefold():
                graphics = f"{graphics} {memory}"
            result.append(f"{graphics} (discrete)")
        elif graphics_type == "integrated":
            result.append(f"{graphics} (integrated)")
    return result

def _chipset(features: dict[str, list[str]]) -> str:
    values = values_for(features, "Chipset")
    if not values or all("soc" in value.casefold() for value in values):
        return ""
    return "\n".join(_unique(values))

def _controls(features: dict[str, list[str]]) -> str:
    return ""

def _multi_mode(features: dict[str, list[str]], html_text: str | None) -> str:
    values = (feature_values_for_heading_preserving_lines(html_text, "Multi-mode") if html_text else []) or values_for(features, "Multi-mode")
    values = [line for value in values for line in value.splitlines() if line.strip()]
    if not values or all(value.lstrip().casefold().startswith("no") for value in values):
        return ""
    return "\n".join(_unique([value.split(":", 1)[0] for value in values]))

def _touchpad_source_values(features: dict[str, list[str]], html_text: str | None) -> list[str]:
    if not html_text:
        return values_for(features, "UltraNav")
    target = "UltraNav".casefold()
    for match in re.finditer(r"<h3\b[^>]*>(.*?)</h3>\s*<div\b[^>]*class=['\"][^'\"]*divFeatureValue[^'\"]*['\"][^>]*>(.*?)</div>", html_text, flags=re.I | re.S):
        heading_html, value_html = match.groups()
        heading = html.unescape(re.sub(r"<[^>]+>", " ", heading_html)).replace("®", "").replace("™", "")
        if " ".join(heading.split()).strip(" *").casefold() != target:
            continue
        value_html = re.sub(r"<span\b(?=[^>]*\bclass\s*=\s*['\"][^'\"]*\bsupText\b[^'\"]*['\"])[^>]*>.*?</span>", "", value_html, flags=re.I | re.S)
        items = re.findall(r"<li\b[^>]*>(.*?)</li>", value_html, flags=re.I | re.S) or [value_html]
        values = []
        for item in items:
            item = re.sub(r"<br\b[^>]*>", "\n", item, flags=re.I)
            value = html.unescape(re.sub(r"<[^>]+>", "", item)).replace("\xa0", " ")
            lines = [" ".join(line.split()) for line in value.splitlines()]
            value = "\n".join(line for line in lines if line)
            if value:
                values.append(value)
        return values
    return values_for(features, "UltraNav")

def _touchpad(features: dict[str, list[str]], html_text: str | None) -> str:
    values = _touchpad_source_values(features, html_text)
    rendered: list[str] = []
    for value in values:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"(?<!\w)[^\s,()]+-button\b[ \t]*", "", value, flags=re.I)
        value = re.sub(r"[ \t]*,?[ \t]*double-tap to open the TrackPoint(?:®)? Quick Menu", "", value, flags=re.I)
        value = re.sub(r"\bpointing device\b|\bmulti-touch\b", "", value, flags=re.I)
        value = value.replace("Glass", "glass")
        source_lines = [" ".join(line.split()) for line in value.splitlines() if line.strip()]
        if source_lines and re.match(r"Models\b.*:$", source_lines[0], flags=re.I):
            source_lines = source_lines[1:]
        if len(source_lines) == 2 and not re.match(r"and\b", source_lines[1], flags=re.I):
            source_lines[1] = "and " + source_lines[1]
        parts = [" ".join(part.split()).strip(" ,.") for part in " ".join(source_lines).split(",")]
        current: list[str] = []
        for part in parts:
            if not part or part.casefold().startswith("supports"):
                continue
            if "inches" in part.casefold():
                if current:
                    rendered.append(", ".join(current).strip(" ,."))
                    current = []
                rendered.append(part)
            else:
                current.append(part)
        if current:
            rendered.append(", ".join(current).strip(" ,."))
    return "\n".join(rendered)

def _battery(features: dict[str, list[str]], tablet: bool) -> str:
    values = values_for(features, "Battery")
    if not values:
        return ""
    out = []
    for value in values:
        value = re.sub(r"^.*?:\s*", "", value)
        capacity = re.search(r"\b\d+(?:\.\d+)?\s*(?:Wh|mAh)\b", value, re.I)
        if not capacity: continue
        rendered = f"{capacity.group(0).replace(' ', '')} battery"
        fast = re.search(r"\bsupports\s+(.+?)(?:\s*\(|$)", value, re.I)
        if fast: rendered += ", " + fast.group(1).strip()
        out.append(rendered)
    life = values_for(features, "Max Battery Life") or values_for(features, "Battery Life")
    if tablet:
        candidates=[]
        for value in life:
            for number in re.findall(r"(\d+(?:\.\d+)?)\s*hr", value, re.I):
                if float(number) < 100: candidates.append((float(number), value))
        if candidates:
            number, branch=max(candidates); out.append(f"{branch} up to {number:g} hr")
    else:
        runtime = non_tablet_battery_life(life)
        if runtime: out.append(runtime)
    return "\n".join(_unique(out))


def _audio(features: dict[str, list[str]], mode: str) -> str:
    out: list[str] = []
    chips = values_for(features, "Audio Chip")
    multiple_conditions = audio_has_multiple_conditions(chips)
    for value in chips:
        out.append(audio_chip_term(value, multiple_conditions) or value)
    for name in ("Speakers", "Microphone"):
        positive, no = positive_values(values_for(features, name))
        out.extend(_star(positive, no))
    return "\n".join(_unique(out))


def _wwan(features: dict[str, list[str]]) -> str:
    values=values_for(features,"WWAN"); generations=[]
    for value in values:
        for generation in ("6G","5G","4G"):
            if generation.casefold() in value.casefold(): generations.append(generation); break
    if not generations: return ""
    generation=max(generations,key=lambda x:int(x[0])); matching=[x for x in values if generation.casefold() in x.casefold()]
    sub=any("sub-6 ghz" in x.casefold() for x in matching); esim=any("with embedded esim" in x.casefold() for x in matching)
    if sub and esim: return f"WWAN upgradable to {generation} Sub-6 GHz with embedded eSIM"
    return "\n".join([f"WWAN upgradable to {generation} Sub-6 GHz"] if sub else [] + [f"WWAN upgradable to {generation} with embedded eSIM"] if esim else [f"WWAN upgradable to {generation}"])


def _security(features: dict[str, list[str]]) -> str:
    out: list[str] = []
    if any(value.lstrip().startswith("ThinkShield is a comprehensive security solution") for value in values_for(features, "ThinkShield")):
        out.append("ThinkShield")
    chip, _ = _security_values(features, "Security Chip")
    if any("discrete tpm 2.0" in x.casefold() for x in chip): out.append("Discrete TPM 2.0")
    elif any("firmware tpm 2.0" in x.casefold() for x in chip): out.append("Firmware TPM 2.0")

    physical_locks, _ = _security_values(features, "Physical Locks")
    for value in physical_locks:
        optional = "optional" in value.casefold()
        value = remove_parentheses(value.split(",", 1)[0])
        if value:
            out.append(value + ("*" if optional else ""))

    smart_card_readers, has_no_smart_card_reader = _security_values(features, "Smart Card Reader")
    out.extend(_star(smart_card_readers, has_no_smart_card_reader))

    fingerprint_readers, has_no_fingerprint_reader = _security_values(features, "Fingerprint Reader")
    for value in fingerprint_readers:
        match_on_chip = "match-on-chip" in value.casefold()
        match = re.search(r"fingerprint reader", value, flags=re.I)
        if match:
            value = value[:match.end()].rstrip()
            if match_on_chip:
                value = value[:match.start()] + "MOC " + value[match.start():]
        if has_no_fingerprint_reader:
            value += "*"
        out.append(value)

    model_note = r"\s*\(\s*(?:[^()]*\bmodels?|\bmodels?\b[^()]*)\s*\)"
    other_security, _ = _security_values(features, "Other Security")
    for value in other_security:
        optional = "optional" in value.casefold() or bool(re.search(model_note, value, flags=re.I))
        value = re.sub(r"\s*\(Optional\)", "", value, flags=re.I)
        value = re.sub(model_note, "", value, flags=re.I)
        value = value.replace(" Image Signal Processor (ISP)", " ISP")
        out.extend(_star([value], optional))
    return "\n".join(_unique(out))


def _ethernet(features: dict[str, list[str]], dt: bool, ts: bool) -> str:
    if ts:
        values = values_for(features, "Optional Ethernet")
        return values[0].split(":", 1)[0] if values else ""
    values = values_for(features, "Onboard Ethernet" if dt else "Ethernet")
    values = [x for x in values if "no onboard ethernet" not in x.casefold()]
    rendered=[]
    for value in values:
        rates=[]
        for needle, output in (("Dual 2.5GbE","2x 2.5GbE"),("Dual Gigabit Ethernet","2x Gigabit Ethernet"),("10GbE","10GbE"),("2.5GbE","2.5GbE"),("Gigabit Ethernet","Gigabit Ethernet")):
            if needle in ("2.5GbE", "Gigabit Ethernet") and f"Dual {needle}".casefold() in value.casefold():
                continue
            if needle.casefold() in value.casefold() and output not in rates: rates.append(output)
        ports=re.findall(r"\b\d+x\s*RJ-45\b",value,re.I)
        if rates: rendered.append(" + ".join(rates)+(f", {ports[0]}" if ports else ""))
    return "\n".join(_unique(rendered))


def _ports(features: dict[str, list[str]], mobile: bool, tablet: bool, dt: bool, ts: bool) -> str:
    if mobile:
        standard,_=positive_values(values_for(features,"Standard Ports")); optional,_=positive_values(values_for(features,"Optional Ports"))
        return "\n".join(_unique(standard+[x+"*" for x in optional]))
    if tablet:
        standard,_=positive_values(values_for(features,"Standard Ports")); optional,_=positive_values(values_for(features,"Optional Ports"))
        return "\n".join(_unique(standard+optional))
    values=[]
    for name in ("Front Ports","Rear Ports"):
        positive,_=positive_values(values_for(features,name)); values.extend(positive)
    for name in ("Optional Front Ports","Optional Rear Ports"):
        positive,_=positive_values(values_for(features,name)); values.extend(x+"*" for x in positive)
    return "\n".join(_unique(values))


def generate(features: dict[str, list[str]], html_text: str | None = None) -> list[tuple[str, str, str]]:
    """Return (L1 feature, L2 feature, short spec) rows owned by this product line."""
    mobile = PRODUCT_LINE in {"commercial_laptop", "consumer_laptop", "smb_laptop"}
    tablet = PRODUCT_LINE == "tablet"; dt = PRODUCT_LINE == "desktop"; ts = PRODUCT_LINE == "thinkstation"
    rows: list[tuple[str,str,str]]=[]
    def add(name: str, value: str, l1: str | None = None) -> None:
        if value: rows.append((l1 or L1.get(name,"SPECIAL FEATURES"),name,value))
    processor = []
    for value in values_for(features, "Processor Family"):
        if "-" in value:
            value = re.sub(r"\s*\([^()]*\)\s*$", "", value)
        processor.append(value.split(";", 1)[0])
    add("Processor", "\n".join(_unique(processor)))
    npu = []
    for value in values_for(features, "NPU"):
        if re.search(r"\(optional\)", value, flags=re.I):
            value = re.sub(r"\(optional\)", "", value, flags=re.I).strip()
            value += "" if value.endswith("*") else "*"
        npu.append(value)
    add("NPU", "\n".join(_unique(npu)))
    add("AI PC Category", _ai_pc_category(features))
    add("Graphics", "\n".join(_graphics(features, html_text)))
    add("Audio",_audio(features,"dt" if dt else "tablet" if tablet else "mobile"))
    if not ts:
        add("Camera", camera_short_spec(values_for(features, "Camera"), PRODUCT_LINE))
    if not dt and not ts: add("Battery",_battery(features,tablet))
    for name in ("Bundled Accessories","Buttons","Charging Time","Cellular Bands","FM Radio","Location Services","Sensors","Wi-Fi Direct","Wi-Fi Display"):
        if (name in {"Bundled Accessories","Buttons","Charging Time","Cellular Bands","FM Radio","Location Services","Sensors","Wi-Fi Direct","Wi-Fi Display"} and not tablet): continue
        vals,no=positive_values(values_for(features,name));
        if name in {"Bundled Accessories","FM Radio","Wi-Fi Direct","Wi-Fi Display","Sensors"} and not vals: continue
        value="\n".join(_star(_unique(vals), no if name=="Bundled Accessories" else False))
        if name=="Cellular Bands" and value: value="For WWAN models:\n"+value
        if name=="Location Services": value="\n".join(_unique([p.strip() + ("*" if "+" not in x and p.strip() else "") for x in vals for p in x.split("+") if not p.strip().casefold().startswith("no")]))
        add(name,value)
    for source,name in (("Case Color","Color"),("Case Material","Case Material"),("Material","Material"),("Dimensions (WxDxH)","Dimensions (WxDxH)"),("Weight","Weight")):
        if name=="Case Material" and not (mobile or tablet): continue
        if name=="Material" and tablet: continue
        if name == "Dimensions (WxDxH)":
            add(name, "\n".join(_dimensions(features, html_text)))
        elif name == "Weight":
            add(name, "\n".join(_weight(features, html_text)))
        else:
            add(name,"\n".join(_unique(values_for(features, source))))
    if not ts:
        values,no=positive_values(values_for(features,"NFC")); add("NFC","\n".join(_star(_unique(values),no)))
        values,no=positive_values(values_for(features,"Pen"));
        if values: add("Pen","\n".join(_star(_unique([remove_parentheses(re.split(r"\bwith\b|\bfor\b|,",x,1,flags=re.I)[0]) for x in values]),True)))
        add("WWAN",_wwan(features))
    if mobile or tablet:
        values,no=positive_values(values_for(features,"Power Adapter")); cleaned=[]
        for x in values:
            x=x.split(",",1)[0] if tablet else remove_parentheses(re.sub(r"\bsupports\s+|,?\s*100-240V,?\s*50-60Hz|\bAC\b","",x,flags=re.I))
            cleaned.append(x)
        add("Power Adapter","\n".join(_star(_unique(cleaned),no or len(cleaned)>1)))
    add("Ports", _ports(features, mobile, tablet, dt, ts))
    add("Ethernet", _ethernet(features, dt, ts))
    add("Security", _security(features))
    if PRODUCT_LINE in {"desktop","thinkstation"}:
        values=values_for(features,"Base Warranty"); candidates=[x for x in values if re.match(r"\d",x)]
        if candidates: add("Base Warranty","Up to "+max(candidates,key=lambda x:float(re.match(r"\d+(?:\.\d+)?",x).group())))
    values,no=positive_values(values_for(features,"Green Certifications")); cleaned=[]
    for x in values:
        optional = "optional" in x.casefold()
        x=remove_parentheses(x.split(". ",1)[0]); cleaned.append(x+("*" if optional else ""))
    add("Green Certifications","\n".join(_unique(cleaned)))
    if ts: add("ISV Certifications",'<p>Please visit <a href="www.thinkworkstations.com/isv-certifications/" target="_blank">ISV certifications for Lenovo Workstations</a></p>')
    if PRODUCT_LINE in {"commercial_laptop","desktop","thinkstation"}:
        values,no=positive_values(values_for(features,"System Management")); add("System Management","\n".join(_star(_unique([remove_parentheses(x) for x in values]),no)))
    if not ts: add("Screen-to-Body Ratio","\n".join(_unique(values_for(features,"Screen-to-Body Ratio"))))
    add("Chipset", _chipset(features))
    add("Controls", _controls(features))
    add("Multi-mode", _multi_mode(features, html_text))
    add("Touchpad", _touchpad(features, html_text))
    add("Docking", _docking(features))
    return rows
