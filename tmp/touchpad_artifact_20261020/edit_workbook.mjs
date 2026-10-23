import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "D:/shortspec_generator";
const inputPath = path.join(root, "release/third_batch_html_260919/h_3rd_com.xlsx");
const outputDir = path.join(root, "tmp/touchpad_artifact_20261020");
const outputPath = path.join(outputDir, "h_3rd_com_checked.xlsx");
const expectedProduct = "ThinkPad_X1_Carbon_Gen_13_Aura_Edition";
const expectedValue = [
  "TrackPoint and glass surface Haptic Touchpad",
  "70.5 x 120 mm (2.78 x 4.72 inches)",
  "TrackPoint and glass surface Trackpad",
  "56.2 x 120 mm (2.21 x 4.72 inches)",
].join("\n");

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItem("All Products");
const original = sheet.getRange("A21:D21").values[0];
if (original[0] !== expectedProduct || original[2] !== "Touchpad") {
  throw new Error(`Unexpected target row: ${JSON.stringify(original)}`);
}
const before = await workbook.render({ sheetName: "All Products", range: "A19:D22", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "before.png"), new Uint8Array(await before.arrayBuffer()));
sheet.getRange("D21").values = [[expectedValue]];
workbook.recalculate();
const check = await workbook.inspect({kind:"region", sheetId:"All Products", range:"A19:D22", maxChars:1800});
console.log(check.ndjson);
const after = await workbook.render({ sheetName: "All Products", range: "A19:D22", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "after.png"), new Uint8Array(await after.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT ${outputPath}`);
