import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "D:/shortspec_generator/outputs/shortspec_comparison";
await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Why Short Specifications Matter");
sheet.showGridLines = false;

sheet.getRange("A1:D1").merge();
sheet.getRange("A1").values = [["Why Short Specifications Matter"]];
sheet.getRange("A2:D2").merge();
sheet.getRange("A2").values = [["Short specifications transform detailed product data into concise, business-ready information."]];

sheet.getRange("A4:D11").values = [
  ["Dimension", "Full Product Specification", "Short Specification", "Business Value"],
  ["Primary purpose", "Provides complete technical and configuration details", "Highlights key configurations and selling points", "Matches information depth to the audience's needs"],
  ["Typical audience", "Product experts, engineers, and technical reviewers", "Sales, marketing, channels, customers, and management", "Enables faster cross-functional communication"],
  ["Content volume", "Comprehensive and often lengthy", "Concise and focused", "Reduces reading and search time"],
  ["Information structure", "Includes all options, conditions, notes, and technical details", "Consolidates the most relevant information using business rules", "Makes product differentiation easier to identify"],
  ["Ease of use", "Suitable for detailed research and technical validation", "Suitable for quick review, comparison, and communication", "Speeds up product launch and sales enablement activities"],
  ["Consistency requirement", "Accuracy of complete source data", "Accuracy, clarity, and consistent wording across products", "Strengthens product-information quality and brand consistency"],
  ["Update impact", "Changes may be distributed across many detailed sections", "Requires controlled summarization after source changes", "Makes traceable, rule-based maintenance essential"],
];

sheet.getRange("A13:D13").merge();
sheet.getRange("A13").values = [["Key message: Short specifications are not simplified copies of full specifications. They are structured business outputs that transform detailed product data into concise, consistent, and usable information."]];

sheet.getRange("A1:D1").format = {
  fill: "#0B1F3A",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("A2:D2").format = {
  fill: "#EAF1F8",
  font: { color: "#1F3A5F", italic: true, size: 11 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("A4:D4").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF", size: 11 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#B8C7D9" },
};
sheet.getRange("A5:D11").format = {
  font: { color: "#1F2937", size: 10 },
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D9E2F3" },
};
sheet.getRange("A5:A11").format = {
  fill: "#F2F6FA",
  font: { bold: true, color: "#1F3A5F", size: 10 },
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D9E2F3" },
};
sheet.getRange("D5:D11").format = {
  fill: "#EEF6F2",
  font: { color: "#1F5136", size: 10 },
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D9E2F3" },
};
sheet.getRange("A13:D13").format = {
  fill: "#FFF4D6",
  font: { bold: true, color: "#704D00", size: 10 },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#E6C76B" },
};

sheet.getRange("A:A").format.columnWidth = 22;
sheet.getRange("B:B").format.columnWidth = 37;
sheet.getRange("C:C").format.columnWidth = 37;
sheet.getRange("D:D").format.columnWidth = 40;
sheet.getRange("1:1").format.rowHeight = 30;
sheet.getRange("2:2").format.rowHeight = 36;
sheet.getRange("4:4").format.rowHeight = 30;
sheet.getRange("5:11").format.rowHeight = 52;
sheet.getRange("13:13").format.rowHeight = 42;
sheet.freezePanes.freezeRows(4);

const inspection = await workbook.inspect({
  kind: "table",
  range: "Why Short Specifications Matter!A1:D13",
  include: "values,formulas",
  tableMaxRows: 13,
  tableMaxCols: 4,
});
console.log(inspection.ndjson);

const preview = await workbook.render({
  sheetName: "Why Short Specifications Matter",
  range: "A1:D13",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(`${outputDir}/why_short_specifications_matter_preview.png`, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/why_short_specifications_matter.xlsx`);
