"""Commercial-laptop-owned HTML rules for the 33 third-batch features."""
from __future__ import annotations

import re

from html_source_rules import additional_third_batch_values, dimensions_values, graphics_values, positive_values, remove_parentheses, values_for

PRODUCT_LINE = "smb_laptop"

L1 = {
    "Processor Family": "PERFORMANCE", "Graphics": "PERFORMANCE", "NPU": "PERFORMANCE", "AI PC Category": "PERFORMANCE", "Chipset": "PERFORMANCE",
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
    names = ["Speakers", "Microphone"] if mode == "tablet" else ["Audio Chip", "Speakers", "Microphone"]
    out=[]
    for name in names:
        values = values_for(features, name)
        positive, no = positive_values(values)
        for value in (values if mode == "dt" else positive):
            value = re.sub(r"\s*optimized with\s*", " ", value, flags=re.I)
            if name == "Audio Chip" and mode != "dt":
                match=re.search(r"(High Definition \(HD\) Audio|SoundWire)",value,re.I)
                if not match: continue
                value=match.group(1)
            out.append(value + ("*" if name == "Microphone" and no and not value.endswith("*") else ""))
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


def _security(features: dict[str, list[str]], workstation: bool) -> str:
    if not workstation: return ""
    out=[]; chip=values_for(features,"Security Chip")
    if any("discrete tpm 2.0" in x.casefold() for x in chip): out.append("Discrete TPM 2.0")
    elif any("firmware tpm 2.0" in x.casefold() for x in chip): out.append("Firmware TPM 2.0")
    for name in ("Physical Locks","Chassis Intrusion Switch","Fingerprint Reader"):
        positive,no=positive_values(values_for(features,name))
        for value in positive:
            value=remove_parentheses(value.split(",",1)[0]) if name=="Physical Locks" else value
            if "optional" in value.casefold() or no: value += "*" if not value.endswith("*") else ""
            out.append(value)
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
            if needle.casefold() in value.casefold() and output not in rates: rates.append(output)
        ports=re.findall(r"\b\d+x\s*RJ-45\b",value,re.I)
        if rates: rendered.append(" + ".join(rates)+(f", {ports[0]}" if ports else ""))
    return "\n".join(_unique(rendered))


def _ports(features: dict[str, list[str]], mobile: bool, tablet: bool, dt: bool, ts: bool) -> str:
    if mobile:
        standard,_=positive_values(values_for(features,"Standard Ports")); optional,_=positive_values(values_for(features,"Optional Ports"))
        return "\n".join(_unique([x.split(",",1)[0] if "thunderbolt" in x.casefold() else x for x in standard]+[x+"*" for x in optional]))
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
    for name in ("Processor Family","AI PC Category","NPU"):
        add(name,"\n".join(_unique(values_for(features,name))))
    add("Graphics", "\n".join(graphics_values(features, html_text, PRODUCT_LINE)))
    add("Audio",_audio(features,"dt" if dt else "tablet" if tablet else "mobile"))
    if not ts:
        camera,no=positive_values(values_for(features,"Camera")); camera=[remove_parentheses(x).replace("Computer Vision on Image Signal Processor", "CV on ISP") for x in camera]
        add("Camera","\n".join(_star(camera,no)))
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
        values = dimensions_values(features, html_text) if name == "Dimensions (WxDxH)" else values_for(features, source)
        add(name,"\n".join(_unique(values)))
    if not ts:
        values,no=positive_values(values_for(features,"NFC")); add("NFC","\n".join(_star(_unique(values),no)))
        values,no=positive_values(values_for(features,"Pen"));
        if values: add("Pen","\n".join(_star(_unique([remove_parentheses(re.split(r"\bwith\b|\bfor\b|,",x,1,flags=re.I)[0]) for x in values]),True)))
        elif no: add("Pen","\n".join(_unique(values_for(features,"Pen"))))
        add("WWAN",_wwan(features))
    if mobile or tablet:
        values,no=positive_values(values_for(features,"Power Adapter")); cleaned=[]
        for x in values:
            x=x.split(",",1)[0] if tablet else remove_parentheses(re.sub(r"\bsupports\s+|,?\s*100-240V,?\s*50-60Hz|\bAC\b","",x,flags=re.I))
            cleaned.append(x)
        add("Power Adapter","\n".join(_star(_unique(cleaned),no or len(cleaned)>1)))
    add("Ports", _ports(features, mobile, tablet, dt, ts))
    add("Ethernet", _ethernet(features, dt, ts))
    if dt or ts: add("Security",_security(features,True))
    if PRODUCT_LINE in {"commercial_laptop","desktop","thinkstation"}:
        values=values_for(features,"Base Warranty"); candidates=[x for x in values if re.match(r"\d",x)]
        if candidates: add("Base Warranty","Up to "+max(candidates,key=lambda x:float(re.match(r"\d+(?:\.\d+)?",x).group())))
    values,no=positive_values(values_for(features,"Green Certifications")); cleaned=[]
    for x in values:
        x=remove_parentheses(x.split(". ",1)[0]); cleaned.append(x+("*" if "optional" in x.casefold() else ""))
    add("Green Certifications","\n".join(_unique(cleaned)))
    if ts: add("ISV Certifications",'<p>Please visit <a href="www.thinkworkstations.com/isv-certifications/" target="_blank">ISV certifications for Lenovo Workstations</a></p>')
    if PRODUCT_LINE in {"commercial_laptop","desktop","thinkstation"}:
        values,no=positive_values(values_for(features,"System Management")); add("System Management","\n".join(_star(_unique([remove_parentheses(x) for x in values]),no)))
    if not ts: add("Screen-to-Body Ratio","\n".join(_unique(values_for(features,"Screen-to-Body Ratio"))))
    for name, value in additional_third_batch_values(features, PRODUCT_LINE):
        add(name, value)
    return rows
