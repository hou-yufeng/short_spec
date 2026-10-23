import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';
const inputPath = 'D:/shortspec_generator/release/third_batch_html_260916/docs/Third_Batch_38_Feature_Matrix.xlsx';
const outputPath = 'D:/shortspec_generator/release/third_batch_html_260916/docs/Third_Batch_38_Feature_Matrix.xlsx';
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const ws = wb.worksheets.getItem('Third Batch Features');
ws.getRange('A1').values = [['Third-Batch ShortSpec Features by Product Line (45 Features)']];
const newRows = [
  ['Bays', '-', '-', '-', '-', 'Included', 'Included'],
  ['Chassis', '-', '-', '-', '-', 'Included', '-'],
  ['Cooling System (Fan & Cooler)', '-', '-', '-', '-', 'Included', '-'],
  ['Expansion Slots', '-', '-', '-', '-', 'Included', 'Included'],
  ['Form Factor', '-', '-', '-', '-', 'Included', 'Included'],
  ['Optical', '-', '-', '-', '-', 'Included', 'Included'],
  ['Power Supply', '-', '-', '-', '-', 'Included', 'Included'],
];
ws.getRange('A40:G40').copyTo(ws.getRange('A41:G47'), 'all');
ws.getRange('A41:G47').values = newRows;
wb.recalculate();
const check = await wb.inspect({kind:'table', sheetId:'Third Batch Features', range:'A1:G47', tableMaxRows:50, tableMaxCols:7, maxChars:12000});
console.log(check.ndjson);
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(outputPath);
console.log('SAVED', outputPath);
