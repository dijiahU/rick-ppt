import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import * as fflate from 'fflate';
import {DOMParser} from '@xmldom/xmldom';
globalThis.DOMParser=DOMParser;
const modules={fflate};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
modules['./attachments']=load('lib/attachments.ts');
const {documentText}=load('lib/document-preview.ts');
const word=text=>fflate.zipSync({'word/document.xml':fflate.strToU8(text),'word/media/ignored.png':new Uint8Array(100)});
const xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>First survey</w:t></w:r></w:p><w:p><w:r><w:t>中文 &amp; English &lt;script&gt;alert(1)&lt;/script&gt;</w:t></w:r></w:p></w:body></w:document>';
assert.deepEqual(documentText(word(xml),'docx'),{text:'First survey\n\n中文 & English <script>alert(1)</script>',truncated:false});
assert.deepEqual(documentText(fflate.strToU8('中文,English\n1,2'),'csv'),{text:'中文,English\n1,2',truncated:false});
const long=documentText(fflate.strToU8('x'.repeat(300001)),'txt');assert.equal(long.text.length,300000);assert.equal(long.truncated,true);
assert.throws(()=>documentText(new Uint8Array(20*1024*1024+1),'txt'));
assert.throws(()=>documentText(word('<!DOCTYPE x [<!ENTITY x "test">]>'+xml),'docx'));
assert.throws(()=>documentText(fflate.zipSync({'other.xml':new Uint8Array(1)}),'docx'));
assert.throws(()=>documentText(new Uint8Array([255]),'txt'));
assert.throws(()=>documentText(word(xml),'pptx'));
const large=fflate.zipSync({'word/document.xml':new Uint8Array(4*1024*1024+1)});assert.throws(()=>documentText(large,'docx'));
if(process.argv[2]){
 const actual=documentText(new Uint8Array(readFileSync(process.argv[2])),'docx');
 assert.ok(actual.text.includes('First survey'));assert.ok(actual.text.includes('第一次'));assert.ok(!actual.truncated);
 console.log(`PASS: actual uploaded course Word document (${actual.text.length} characters) reads in full`);
}
console.log('PASS: Word paragraphs, bilingual text/entities, text/CSV, explicit truncation, unsupported formats and bounded Office/XML parsing');
