import {readFileSync,statSync,writeFileSync} from 'node:fs';
import {gzipSync} from 'node:zlib';
const manifest=JSON.parse(readFileSync('dist/.vite/manifest.json','utf8'));
function visit(key,seen){if(seen.has(key))return;seen.add(key);for(const child of manifest[key]?.imports??[])visit(child,seen);}
const seen=new Set();for(const key of Object.keys(manifest))if(manifest[key].name==='main'||manifest[key].isEntry)visit(key,seen);
const core=[...seen].map(k=>manifest[k].file);
const size=core.reduce((n,f)=>n+gzipSync(readFileSync('dist/'+f)).length,0);
const chunks=Object.fromEntries(Object.values(manifest).filter(v=>v.file.endsWith('.js')).map(v=>[v.file,{bytes:statSync('dist/'+v.file).size,gzip:gzipSync(readFileSync('dist/'+v.file)).length}]));
const assets=JSON.parse(readFileSync('dist/packs/manifest.json','utf8')).assets;
const featurePacks=Object.fromEntries(['code','three','ml','map','math'].map(name=>{
 // Rollup may merge the code entry into Monaco's anonymous shared chunk. Its
 // lazy language entries still reference that chunk in the build manifest.
 // Count these on-demand JS files as part of the code pack too.
 const imports=new Set();for(const key of Object.keys(manifest))if(key.startsWith(`src/feature-packs/${name}/`)||(name==='code'&&key.startsWith('node_modules/monaco-editor/')))visit(key,imports);
 const files=[...imports].filter(key=>!seen.has(key)).map(key=>manifest[key].file).filter(file=>file.endsWith('.js'));
 if(!files.length)throw new Error(`Missing build chunks for feature pack ${name}`);
 const cssFiles=[...new Set([...imports].filter(key=>!seen.has(key)).flatMap(key=>manifest[key].css??[]))];
 const bundledAssets=[...new Set([...imports].filter(key=>!seen.has(key)).flatMap(key=>manifest[key].assets??[]))];
 return [name,{files,javascriptGzipBytes:files.reduce((n,file)=>n+(chunks[file]?.gzip??0),0),cssGzipBytes:cssFiles.reduce((n,file)=>n+gzipSync(readFileSync('dist/'+file)).length,0),bundledAssetBytes:bundledAssets.reduce((n,file)=>n+statSync('dist/'+file).size,0),localAssetBytes:assets.filter(asset=>asset.path.startsWith(`packs/${name}/`)).reduce((n,asset)=>n+asset.bytes,0)}];
}));
const report={coreGzipBytes:size,coreFiles:core,limit:300000,chunks,featurePacks};
writeFileSync('dist/bundle-sizes.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
if(size>report.limit)throw new Error('Core bundle size regression');
