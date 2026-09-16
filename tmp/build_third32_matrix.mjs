import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const output = "D:/shortspec_generator/release/third_batch_html_260915_33_r1/docs/Third_Batch_33_Feature_Matrix.xlsx";
const lines = ["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Tablet", "Desktop", "ThinkStation"];
const features = ["AI PC Category", "Audio", "Base Warranty", "Battery", "Bundled Accessories", "Buttons", "Camera", "Case Material", "Cellular Bands", "Charging Time", "Color", "Dimensions (WxDxH)", "Ethernet", "FM Radio", "Graphics", "Green Certifications", "ISV Certifications", "Location Services", "Material", "NFC", "NPU", "Pen", "Ports", "Power Adapter", "Processor Family", "Security", "Sensors", "Screen-to-Body Ratio", "System Management", "Weight", "Wi-Fi Direct", "Wi-Fi Display", "WWAN"];
const tabletOnly = new Set(["Bundled Accessories", "Buttons", "Cellular Bands", "Charging Time", "FM Radio", "Location Services", "Sensors", "Wi-Fi Direct", "Wi-Fi Display"]);
const noThinkStation = new Set(["Camera", "NFC", "Pen", "Screen-to-Body Ratio", "WWAN"]);
const noDtTs = new Set(["Battery", "Power Adapter", "Case Material"]);
const restricted = {"Base Warranty": new Set(["Desktop", "ThinkStation"]), "ISV Certifications": new Set(["ThinkStation"]), "Material": new Set(["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Desktop", "ThinkStation"]), "System Management": new Set(["Commercial Laptop", "Desktop", "ThinkStation"])};
function applies(feature, line) { if (restricted[feature]) return restricted[feature].has(line); if (tabletOnly.has(feature)) return line === "Tablet"; if (noThinkStation.has(feature) && line === "ThinkStation") return false; if (noDtTs.has(feature) && (line === "Desktop" || line === "ThinkStation")) return false; return true; }
const wb = Workbook.create(); const ws = wb.worksheets.add("Third Batch Features"); ws.showGridLines = false;
ws.mergeCells("A1:G1"); ws.getRange("A1").values = [["Third-Batch HTML ShortSpec Features by Product Line (33 Features)"]]; ws.getRange("A1").format = {font:{name:"Arial",size:14,bold:true,color:"#1F1F1F"},verticalAlignment:"center"};
ws.getRange("A3:G3").values = [["Feature", ...lines]];
const rows = features.map(feature => [feature, ...lines.map(line => applies(feature,line) ? "Included" : "N/A")]);
ws.getRange(`A4:G${rows.length+3}`).values = rows;
ws.getRange("A3:G3").format = {fill:"#1F4E78",font:{name:"Arial",size:10,bold:true,color:"#FFFFFF"},horizontalAlignment:"center",verticalAlignment:"center"};
ws.getRange(`A4:A${rows.length+3}`).format.font = {name:"Arial",size:10,bold:true}; ws.getRange(`B4:G${rows.length+3}`).format.horizontalAlignment="center";
ws.getRange(`A3:G${rows.length+3}`).format.borders={preset:"all",style:"thin",color:"#D9E2F3"}; ws.getRange("A:A").format.columnWidth=31; ws.getRange("B:G").format.columnWidth=20; ws.getRange("A1:G1").format.rowHeight=26; ws.freezePanes.freezeRows(3);
ws.getRange(`B4:G${rows.length+3}`).conditionalFormats.add("containsText",{text:"N/A",format:{fill:"#F2F2F2",font:{color:"#666666"}}});
await wb.recalculate(); const check=await wb.inspect({kind:"table",range:`Third Batch Features!A1:G${rows.length+3}`,include:"values",tableMaxRows:35,tableMaxCols:7}); console.log(check.ndjson);
const preview=await wb.render({sheetName:"Third Batch Features",range:`A1:G${rows.length+3}`,scale:1.5,format:"png"}); await fs.writeFile("D:/shortspec_generator/analysis_output/third33_matrix_preview.png",new Uint8Array(await preview.arrayBuffer()));
const file=await SpreadsheetFile.exportXlsx(wb); await file.save(output);
