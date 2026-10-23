import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load('D:/shortspec_generator/release/third_batch_html_260916/docs/Third_Batch_38_Feature_Matrix.xlsx'));
const img = await wb.render({sheetName:'Third Batch Features', range:'A1:G40', scale:1.5, format:'png'});
await fs.writeFile('D:/shortspec_generator/tmp/matrix_edit/before.png', new Uint8Array(await img.arrayBuffer()));
console.log('RENDERED_BEFORE');
