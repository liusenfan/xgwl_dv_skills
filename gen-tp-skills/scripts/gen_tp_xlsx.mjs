// XLSX presentation adapter. Content comes from the validated plan, never the VU reference.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const [input, output, ...flags] = process.argv.slice(2);
if (!input || !output) throw new Error('Usage: gen_tp_xlsx.mjs plan.json output.xlsx [--node-modules DIR] [--preview-dir DIR]');
const option = key => {const i=flags.indexOf(key); return i < 0 ? undefined : flags[i+1];};
const runtimeModules = option('--node-modules') || process.env.TP_NODE_MODULES;
const previewDir = option('--preview-dir');
const resolver = runtimeModules ? createRequire(path.join(path.resolve(runtimeModules), '__tp_loader__.cjs')) : createRequire(import.meta.url);
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(resolver.resolve('@oai/artifact-tool')).href);
const profile = JSON.parse(await fs.readFile(new URL('../assets/xlsx-style.json', import.meta.url), 'utf8'));
const data = JSON.parse(await fs.readFile(input, 'utf8'));
const workbook = Workbook.create();
const categories = data.layout?.categories || [...new Set(data.rows.map(row => row[0]))];
const status = data.meta.find(text => /^规划状态[：:]/.test(text))?.replace(/^规划状态[：:]\s*/, '').split(/[；;]/)[0] || '待确认';
const usedNames = new Set(['plan notes', ...(data.layout?.issue_sheets || []).map(s=>s.name.toLowerCase())]);
const pointStatus = row => data.layout?.point_status[row[4]] ?? status;
const sheetName = category => {
  let base = category.replace(/[\\/?*\[\]:]/g, '_').replace(/^'+|'+$/g,'').trim() || 'Scenarios';
  let candidate = base.slice(0,31), n=1;
  while (usedNames.has(candidate.toLowerCase())) {
    const suffix = '_' + (++n);
    candidate = base.slice(0,31-suffix.length)+suffix;
  }
  usedNames.add(candidate.toLowerCase());
  return candidate;
};
// Values remain literal text; strings resembling formulas must never execute.
const literal = value => String(value).startsWith('=') ? "'" + value : value;
const visualText = value => String(value).replace(/<br\s*\/?\s*>/gi,'\n');
const widthUnits = text => [...text].reduce((sum,c) => sum+(c.charCodeAt(0)>255?2:1),0);
function rowHeight(values,widths,header=false) {
  const lines = Math.max(...values.map((value,i) => visualText(value).split('\n').reduce((sum,line) => sum+Math.max(1,Math.ceil(widthUnits(line)/Math.max(8,widths[i]-3))),0)));
  return Math.min(409, Math.max(header?34:28,lines*15+12));
}
function createSheet(name, headers, records, widths) {
  const sheet = workbook.worksheets.add(name);
  const values = [headers, ...records].map(row => row.map(value => literal(visualText(value))));
  const range = sheet.getRangeByIndexes(0,0,values.length,headers.length);
  range.values = values;
  range.setNumberFormat('@');
  range.format.font = {name:profile.font,size:profile.bodySize,color:profile.bodyColor};
  range.format.wrapText=true;
  range.format.horizontalAlignment='left';
  range.format.verticalAlignment='top';
  const header=sheet.getRangeByIndexes(0,0,1,headers.length);
  header.format.fill=profile.headerFill;
  header.format.font={name:profile.font,size:profile.headerSize,bold:true,color:profile.headerColor};
  header.format.horizontalAlignment='center';
  header.format.verticalAlignment='center';
  widths.forEach((width,i)=>{sheet.getRangeByIndexes(0,i,values.length,1).format.columnWidth=width;});
  values.forEach((row,i)=>{sheet.getRangeByIndexes(i,0,1,headers.length).format.rowHeight=rowHeight(row,widths,i===0);});
  // The supplied reference uses unmerged columns and ordinary gridlines.
  sheet.showGridLines=true;
  sheet.freezePanes.freezeRows(1);
  return sheet;
}
const sheets=[];
for (const category of categories) {
  const records=data.rows.filter(row=>row[0]===category).map(row=>profile.columns.map(col=>col.source==='status'?pointStatus(row):row[col.source]));
  sheets.push(createSheet(sheetName(category),profile.columns.map(col=>col.name),records,profile.columns.map(col=>col.width)));
}
for (const spec of data.layout?.issue_sheets || []) {
  sheets.push(createSheet(spec.name,spec.headers,spec.rows,spec.widths));
}
// Keep every remaining metadata/appendix record. Structured issues have their own sheets.
const notes=[];
for(const [section,item,details] of data.notes) {
  const text=visualText(details);
  let remaining=text;
  while(remaining.length>950) {
    let cut=remaining.lastIndexOf('\n',950);
    if(cut<450) cut=950; else cut+=1;
    notes.push([section,item,remaining.slice(0,cut)]);
    remaining=remaining.slice(cut);
  }
  notes.push([section,item,remaining]);
}
sheets.push(createSheet('Plan Notes',['section','item','details'],notes,[34,42,110]));
workbook.recalculate();
// Verify all values in memory before export, not just representative cell addresses.
for(let i=0;i<categories.length;i++) {
  const expected=data.rows.filter(row=>row[0]===categories[i]);
  if (!expected.length) continue;
  const actual=sheets[i].getRangeByIndexes(1,0,expected.length,profile.columns.length).values;
  if(actual.length!==expected.length) throw new Error('Scenario count mismatch');
  for(let r=0;r<expected.length;r++) for(let c=0;c<profile.columns.length;c++) {
    const source=profile.columns[c].source;
    const wanted=visualText(source==='status'?pointStatus(expected[r]):expected[r][source]);
    const got=String(actual[r][c]);
    if(got!==wanted && got!==literal(wanted)) throw new Error(`Value mismatch ${sheets[i].name}:${r+2}:${c+1}`);
  }
}
const inspect=await workbook.inspect({kind:'table',range:`'${sheets[0].name.replace(/'/g,"''")}'!A1:C3`,include:'values,formulas',tableMaxRows:3,tableMaxCols:3});
console.log(inspect.ndjson);
const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'export error scan'});
console.log(errors.ndjson);
if(previewDir) {
  await fs.mkdir(previewDir,{recursive:true});
  for(let i=0;i<sheets.length;i++) {
    const preview=await workbook.render({sheetName:sheets[i].name,range:'A1:C3',scale:1,format:'png'});
    await fs.writeFile(path.join(previewDir,`sheet-${i+1}.png`),new Uint8Array(await preview.arrayBuffer()));
  }
  // Review the right-hand check/traceability fields too.
  const preview=await workbook.render({sheetName:sheets[0].name,range:'J1:N3',scale:1,format:'png'});
  await fs.writeFile(path.join(previewDir,'checks.png'),new Uint8Array(await preview.arrayBuffer()));
}
await fs.mkdir(path.dirname(path.resolve(output)),{recursive:true});
await (await SpreadsheetFile.exportXlsx(workbook)).save(output);
console.log(JSON.stringify({output,points:data.rows.length,sheets:sheets.map(s=>s.name)}));
// Record successful completion only after all requested previews and export writes.
await fs.writeFile(output.replace(/\.xlsx$/i,'.complete.json'),JSON.stringify({points:data.rows.length,complete:true}));
