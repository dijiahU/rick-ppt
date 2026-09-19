import {cp,copyFile,mkdir,readFile,writeFile,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve,relative,join} from 'node:path';
const root=resolve(import.meta.dirname,'..'),dist=join(root,'dist'),records=[];
async function copy(source,target){await mkdir(join(dist,target,'..'),{recursive:true});const input=join(root,source),output=join(dist,target);await copyFile(input,output);const bytes=await readFile(output);records.push({path:target,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});}
await copy('src/feature-packs/code/code-runner.worker.js','packs/code/code-runner.worker.js');
for(const name of ['pyodide.js','pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','pyodide-lock.json','python_stdlib.zip'])await copy(`node_modules/pyodide/${name}`,`packs/code/pyodide/${name}`);
for(const name of ['ort-wasm-simd-threaded.jsep.mjs','ort-wasm-simd-threaded.jsep.wasm'])await copy(`node_modules/onnxruntime-web/dist/${name}`,`packs/ml/${name}`);
for(const name of ['maplibre-gl-worker.mjs','maplibre-gl-shared.mjs'])await copy(`node_modules/maplibre-gl/dist/${name}`,`packs/map/${name}`);
const packages={};for(const name of ['three','monaco-editor','pyodide','onnxruntime-web','maplibre-gl','katex','es-module-lexer'])packages[name]=JSON.parse(await readFile(join(root,'node_modules',name,'package.json'),'utf8')).version;
await writeFile(join(dist,'packs','manifest.json'),JSON.stringify({schemaVersion:1,packages,assets:records,totalBytes:records.reduce((n,a)=>n+a.bytes,0)},null,2)+'\n');
console.log(`Local optional pack assets: ${records.length} files, ${(records.reduce((n,a)=>n+a.bytes,0)/1024/1024).toFixed(2)} MiB. Loaded only on demand.`);
