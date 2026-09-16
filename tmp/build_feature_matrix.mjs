import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputPath = "D:/shortspec_generator/release/third_batch_html_260915/docs/ShortSpec_Feature_Matrix.xlsx";
const lines = ["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Tablet", "Desktop", "ThinkStation"];
const existing = ["Storage", "WLAN + Bluetooth", "Display", "Memory", "Operating System", "Special Features", "Keyboard", "Other Certifications"];
const third = ["AI PC Category", "Audio", "Base Warranty", "Battery", "Bundled Accessories", "Buttons", "Camera", "Case Material", "Cellular Bands", "Charging Time", "Color", "Dimensions (WxDxH)", "Ethernet", "FM Radio", "Graphics", "Green Certifications", "ISV Certifications", "Location Services", "Material", "NFC", "NPU", "Pen", "Ports", "Power Adapter", "Processor Family", "Security", "Sensors", "Screen-to-Body Ratio", "System Management", "Weight", "Wi-Fi Direct", "Wi-Fi Display", "WWAN"];
const tabletOnly = new Set(["Bundled Accessories", "Buttons", "Cellular Bands", "Charging Time", "FM Radio", "Location Services", "Sensors", "Wi-Fi Direct", "Wi-Fi Display"]);
const noThinkStation = new Set(["Camera", "NFC", "Pen", "Screen-to-Body Ratio", "WWAN"]);
const noDtTs = new Set(["Battery", "Power Adapter", "Case Material"]);
const mobileOnly = new Set(["Case Material"]);
const special = {
  "Base Warranty": new Set(["Desktop", "ThinkStation"]),
  "ISV Certifications": new Set(["ThinkStation"]),
  "Material": new Set(["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Desktop", "ThinkStation"]),
  "System Management": new Set(["Commercial Laptop", "Desktop", "ThinkStation"]),
  "Keyboard": new Set(["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Tablet"]),
  "Other Certifications": new Set(["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Tablet", "Desktop"]),
  "Display": new Set(["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Tablet", "Desktop"]),
};
function applies(feature, line) {
  if (special[feature]) return special[feature].has(line);
  if (tabletOnly.has(feature)) return line === "Tablet";
  if (noThinkStation.has(feature) && line === "ThinkStation") return false;
  if (noDtTs.has(feature) && (line === "Desktop" || line === "ThinkStation")) return false;
  if (mobileOnly.has(feature) && !["Commercial Laptop", "Consumer Laptop", "SMB Laptop", "Tablet"].includes(line)) return false;
  return true;
}
const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Feature Matrix");
sheet.showGridLines = false;
sheet.getRange("A1:G1").merge();
sheet.getRange("A1").values = [["HTML ShortSpec Feature Coverage by Product Line"]];
sheet.getRange("A1").format = { font: { name: "Arial", size: 14, bold: true, color: "#1F1F1F" }, horizontalAlignment: "left", verticalAlignment: "center" };
sheet.getRange("A3:G3").values = [["Feature", ...lines]];
const rows = [
  ...existing.map(feature => [feature, ...lines.map(line => applies(feature, line) ? "已完成" : "不适用")]),
  ...third.map(feature => [feature, ...lines.map(line => applies(feature, line) ? "第三批" : "不适用")]),
];
sheet.getRange(`A4:G${rows.length + 3}`).values = rows;
sheet.getRange(`A3:G${rows.length + 3}`).format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
sheet.getRange("A3:G3").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center" };
sheet.getRange(`A4:A${rows.length + 3}`).format.font = { name: "Arial", size: 10, bold: true, color: "#1F1F1F" };
sheet.getRange(`B4:G${rows.length + 3}`).format.horizontalAlignment = "center";
sheet.getRange(`A3:G${rows.length + 3}`).format.borders = { preset: "inside", style: "thin", color: "#D9E2F3" };
sheet.getRange(`A3:G${rows.length + 3}`).format.borders = { preset: "outside", style: "thin", color: "#1F4E78" };
sheet.getRange(`B4:G${rows.length + 3}`).conditionalFormats.add("containsText", { text: "第三批", format: { fill: "#E2F0D9", font: { color: "#375623" } } });
sheet.getRange(`B4:G${rows.length + 3}`).conditionalFormats.add("containsText", { text: "不适用", format: { fill: "#F2F2F2", font: { color: "#666666" } } });
sheet.getRange("A:A").format.columnWidth = 30;
sheet.getRange("B:G").format.columnWidth = 20;
sheet.getRange("A1:G1").format.rowHeight = 26;
sheet.freezePanes.freezeRows(3);
await workbook.recalculate();
await fs.mkdir("D:/shortspec_generator/release/third_batch_html_260915/docs", { recursive: true });
const check = await workbook.inspect({ kind: "table", range: `Feature Matrix!A1:G${rows.length + 3}`, include: "values", tableMaxRows: 45, tableMaxCols: 7 });
console.log(check.ndjson);
const preview = await workbook.render({ sheetName: "Feature Matrix", range: `A1:G${rows.length + 3}`, scale: 1.5, format: "png" });
await fs.writeFile("D:/shortspec_generator/analysis_output/feature_matrix_preview.png", new Uint8Array(await preview.arrayBuffer()));
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
