import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "D:/shortspec_generator";
const outputDir = path.join(root, "tmp/touchpad_con_smb_artifact_20261020");
const cases = [
  {
    config: "con",
    row: 18,
    product: "IdeaPad_Slim_5_Ultra_14ILL11",
    value: "Mylar surface touchpad\n75 x 120 mm (2.95 x 4.72 inches)",
  },
  {
    config: "smb",
    row: 20,
    product: "ThinkBook_16p_G6_IAX",
    value: [
      "glass surface Haptic Touchpad",
      "80 x 135 mm (3.15 x 5.31 inches)",
      "glass surface touchpad",
      "80 x 135 mm (3.15 x 5.31 inches)",
    ].join("\n"),
  },
];

for (const item of cases) {
  const inputPath = path.join(root, `release/third_batch_html_260919/h_3rd_${item.config}.xlsx`);
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
  const sheet = workbook.worksheets.getItem("All Products");
  const original = sheet.getRange(`A${item.row}:D${item.row}`).values[0];
  if (original[0] !== item.product || original[2] !== "Touchpad") {
    throw new Error(`Unexpected target row in ${item.config}: ${JSON.stringify(original)}`);
  }
  const view = `A${item.row - 2}:D${item.row + 1}`;
  const before = await workbook.render({sheetName:"All Products", range:view, scale:1, format:"png"});
  await fs.writeFile(path.join(outputDir, `${item.config}_before.png`), new Uint8Array(await before.arrayBuffer()));
  sheet.getRange(`D${item.row}`).values = [[item.value]];
  workbook.recalculate();
  const check = await workbook.inspect({kind:"region", sheetId:"All Products", range:view, maxChars:1200});
  console.log(item.config, check.ndjson);
  const after = await workbook.render({sheetName:"All Products", range:view, scale:1, format:"png"});
  await fs.writeFile(path.join(outputDir, `${item.config}_after.png`), new Uint8Array(await after.arrayBuffer()));
  const output = await SpreadsheetFile.exportXlsx(workbook);
  const outputPath = path.join(outputDir, `h_3rd_${item.config}_checked.xlsx`);
  await output.save(outputPath);
  console.log(`OUTPUT ${outputPath}`);
}
