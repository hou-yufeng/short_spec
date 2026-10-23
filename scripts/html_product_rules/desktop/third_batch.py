"""Commercial-laptop-owned HTML rules for the 33 third-batch features."""
from __future__ import annotations

import re

from html_source_rules import audio_chip_term, audio_has_multiple_conditions, camera_short_spec, feature_groups_for_structure, feature_table_rows, feature_table_rows_for_heading, feature_values_for_heading_preserving_lines, positive_values, remove_parentheses, values_for

PRODUCT_LINE = "desktop"

L1 = {
    "Processor": "PERFORMANCE", "Graphics": "PERFORMANCE", "NPU": "PERFORMANCE", "AI PC Category": "PERFORMANCE", "Chipset": "PERFORMANCE", "Optical": "PERFORMANCE",
    "Bays": "DESIGN", "Chassis": "DESIGN", "Cooling System (Fan & Cooler)": "DESIGN", "Expansion Slots": "DESIGN", "Form Factor": "DESIGN",
    "Audio": "MULTIMEDIA", "Camera": "MULTIMEDIA", "Battery": "MOBILITY", "Charging Time": "MOBILITY",
    "Power Adapter": "MOBILITY", "Power Supply": "PERFORMANCE", "Dimensions (WxDxH)": "DESIGN", "Weight": "DESIGN", "Color": "DESIGN",
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


def _ai_pc_category(features: dict[str, list[str]]) -> str:
    values = values_for(features, "AI PC Category")
    has_no = any(value.lstrip().casefold().startswith("no") for value in values)
    return "\n".join(_star(_unique([value for value in values if not value.lstrip().casefold().startswith("no")]), has_no))

def _dimensions(features: dict[str, list[str]], html_text: str | None) -> list[str]:
    rows = feature_table_rows_for_heading(html_text, "Dimensions (WxDxH)", preserve_linebreaks=True) if html_text else []
    rows = [row for row in rows if row.get("dimensions")]
    if not rows:
        return (feature_values_for_heading_preserving_lines(html_text, "Dimensions (WxDxH)") if html_text else []) or values_for(features, "Dimensions (WxDxH)")
    tiny_only = next((row for row in rows if "tiny only" in row.get("models", "").casefold()), None)
    if tiny_only:
        return [f"Tiny only:\n{tiny_only['dimensions']}"]
    if len(rows) == 1:
        return [rows[0]["dimensions"]]
    return [f"{row.get('models', '')}:\n{row['dimensions']}" for row in rows]


def _weight(features: dict[str, list[str]], html_text: str | None) -> list[str]:
    rows = feature_table_rows_for_heading(html_text, "Weight", preserve_linebreaks=True) if html_text else []
    if rows:
        return [
            f"{row['models']}: {row['weight'][0].lower()}{row['weight'][1:]}"
            for row in rows
            if row.get("models") and row.get("weight")
        ]
    return (feature_values_for_heading_preserving_lines(html_text, "Weight") if html_text else []) or values_for(features, "Weight")


def _power_supply(html_text: str | None) -> list[str]:
    rows = feature_table_rows_for_heading(html_text, "Power Supply") if html_text else []
    result: list[str] = []
    for row in rows:
        power = row.get("power", "").strip()
        if not power or power.lstrip().casefold().startswith("no"):
            continue
        efficiency = row.get("efficiency", "").strip()
        power_type = row.get("type", "").strip()
        if "fixed" in power_type.casefold():
            power_type = "PSU"
        elif power_type:
            power_type = power_type[0].lower() + power_type[1:]
        key_feature = re.search(r"80\s+PLUS\s+[A-Za-z]+\s+qualified", row.get("key features", ""), flags=re.I)
        value = " ".join(part for part in (power, efficiency, power_type) if part)
        if key_feature:
            value += f", {key_feature.group(0)}"
        result.append(value)
    return _unique(result)


def _power_supply_short_spec(html_text: str | None) -> str:
    items = _power_supply(html_text)
    if not items:
        return ""
    separator = " or " if len(items) == 2 else ", "
    value = separator.join(items)
    psu_matches = list(re.finditer(r"\bPSU\b", value, flags=re.I))
    if len(psu_matches) > 1:
        last_psu = psu_matches[-1].start()
        value = re.sub(r"\bPSU\b", "", value[:last_psu], flags=re.I) + value[last_psu:]
        value = re.sub(r" {2,}", " ", value)
        value = re.sub(r" +,", ",", value)
    return value


def _optical(features: dict[str, list[str]]) -> str:
    keywords = ("DVD±RW", "DVD-ROM", "Blu-ray")
    values = values_for(features, "Optical")
    usb_external = any("usb external" in value.casefold() for value in values)
    result: list[str] = []
    for value in values:
        matches = [
            (match.start(), keyword)
            for keyword in keywords
            for match in re.finditer(re.escape(keyword), value, flags=re.I)
        ]
        result.extend(keyword for _, keyword in sorted(matches))
    result = _unique(result)
    if len(result) == 2:
        output = " or ".join(result)
    elif len(result) == 3:
        output = f"{result[0]}, {result[1]}, or {result[2]}"
    else:
        output = result[0] if result else ""
    return f"{output}, USB external" if output and usb_external else output


def _bays(features: dict[str, list[str]]) -> str:
    values = values_for(features, "Bays")
    return "\n".join(_unique([value + "*" if re.search(r"\s+\(optional", value, re.I) and not value.endswith("*") else value for value in values if not value.lstrip().casefold().startswith("no")]))


def _direct_feature(features: dict[str, list[str]], name: str) -> str:
    return "\n".join(values_for(features, name))


def _expansion_slots(features: dict[str, list[str]]) -> str:
    result: list[str] = []
    for value in values_for(features, "Expansion Slots"):
        value = re.split(r",\s*(?:full|low)\b", value, maxsplit=1, flags=re.I)[0].strip()
        if value:
            result.append(value)
    return "\n".join(_unique(result))


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

def _multi_mode(features: dict[str, list[str]]) -> str:
    return ""

def _touchpad(features: dict[str, list[str]]) -> str:
    return ""

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
        candidates=[]
        for value in life:
            if "mobilemark" in value.casefold():
                for number in re.findall(r"(\d+(?:\.\d+)?)\s*hr", value, re.I): candidates.append(float(number))
        if candidates: out.append(f"Up to {max(candidates):g} hr")
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
    values = values_for(features, "WWAN")
    has_no = any(value.lstrip().casefold().startswith("no") for value in values)
    result: list[str] = []
    for value in values:
        if value.lstrip().casefold().startswith("no") or "," not in value:
            continue
        phrases = [phrase.strip() for phrase in value.split(",")]
        selected = [phrases[1]]
        if len(phrases) >= 4 and "esim" in phrases[3].casefold():
            selected.append(phrases[3])
        result.append(" ".join(selected) + ("*" if has_no else ""))
    return "\n".join(dict.fromkeys(result))


def _security(features: dict[str, list[str]], workstation: bool) -> str:
    if not workstation: return ""
    out=[]
    chip, no_chip = positive_values(values_for(features, "Security Chip"))
    discrete_chip = [value for value in chip if value.lstrip().casefold().startswith("discrete tpm")]
    out.extend(_star(discrete_chip or chip, no_chip))
    for name in ("Physical Locks","Chassis Intrusion Switch","Fingerprint Reader"):
        positive,no=positive_values(values_for(features,name))
        for value in positive:
            optional = "optional" in value.casefold()
            value = remove_parentheses(value)
            if value: out.extend(_star([value], no or optional))
    model_note = r"\s*\(\s*(?:[^()]*\bmodels?|\bmodels?\b[^()]*)\s*\)"
    other_security, _ = positive_values(values_for(features, "Other Security"))
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
    if dt and not values:
        values = values_for(features, "Ethernet")
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


def _ports(html_text: str | None) -> list[tuple[str, str]]:
    if not html_text:
        return []
    groups: dict[str, tuple[str, list[str], list[str]]] = {}
    for heading, values in feature_groups_for_structure(html_text, "Ports"):
        heading = re.sub(r"\*+$", "", heading).strip()
        if "ports" not in heading.casefold():
            continue
        optional = "optional" in heading.casefold()
        name = re.sub(r"\bOptional\s+", "", heading, flags=re.I).strip()
        key = name.casefold()
        if key not in groups:
            groups[key] = (name, [], [])
        regular_values, optional_values = groups[key][1:]
        target = optional_values if optional else regular_values
        target.extend(value + "*" if optional else value for value in values)
    return [(name, "\n".join(regular + optional)) for name, regular, optional in groups.values()]


def generate(features: dict[str, list[str]], html_text: str | None = None) -> list[tuple[str, str, str]]:
    """Return (L1 feature, L2 feature, short spec) rows owned by this product line."""
    mobile = PRODUCT_LINE in {"commercial_laptop", "consumer_laptop", "smb_laptop"}
    tablet = PRODUCT_LINE == "tablet"; dt = PRODUCT_LINE == "desktop"; ts = PRODUCT_LINE == "thinkstation"
    rows: list[tuple[str,str,str]]=[]
    def add(name: str, value: str, l1: str | None = None) -> None:
        if value: rows.append((l1 or L1.get(name,"SPECIAL FEATURES"),name,value))
    add("Processor", "\n".join(_unique(values_for(features, "Processor Family"))))
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
        if not dt:
            values,no=positive_values(values_for(features,"Pen"));
            if values: add("Pen","\n".join(_star(_unique([remove_parentheses(re.split(r"\bwith\b|\bfor\b|,",x,1,flags=re.I)[0]) for x in values]),True)))
        add("WWAN",_wwan(features))
    if mobile or tablet:
        values,no=positive_values(values_for(features,"Power Adapter")); cleaned=[]
        for x in values:
            x=x.split(",",1)[0] if tablet else remove_parentheses(re.sub(r"\bsupports\s+|,?\s*100-240V,?\s*50-60Hz|\bAC\b","",x,flags=re.I))
            cleaned.append(x)
        add("Power Adapter","\n".join(_star(_unique(cleaned),no or len(cleaned)>1)))
    if dt:
        add("Power Supply", _power_supply_short_spec(html_text))
        add("Optical", _optical(features))
        add("Bays", _bays(features))
        add("Chassis", _direct_feature(features, "Chassis"))
        add("Cooling System (Fan & Cooler)", _direct_feature(features, "Cooling System (Fan & Cooler)"))
        add("Expansion Slots", _expansion_slots(features))
        add("Form Factor", _direct_feature(features, "Form Factor"))
    for name, value in _ports(html_text):
        add(name, value, l1="CONNECTIVITY")
    add("Ethernet", _ethernet(features, dt, ts))
    if dt or ts: add("Security",_security(features,True))
    if PRODUCT_LINE in {"commercial_laptop","desktop","thinkstation"}:
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
    add("Multi-mode", _multi_mode(features))
    add("Touchpad", _touchpad(features))
    return rows
