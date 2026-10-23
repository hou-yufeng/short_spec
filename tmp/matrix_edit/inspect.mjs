import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const path = 'D:/shortspec_generator/release/third_batch_html_260916/docs/Third_Batch_38_Feature_Matrix.xlsx';
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
console.log((await wb.inspect({kind:'workbook,sheet,table', maxChars:12000, tableMaxRows:12, tableMaxCols:12})).ndjson);
for (const ws of wb.worksheets.items) {
  console.log('SHEET', ws.name);
  console.log((await wb.inspect({kind:'region', sheetId:ws.name, range:'A1:Z80', maxChars:20000})).ndjson);
}
