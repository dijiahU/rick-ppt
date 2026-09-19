import {describe,it,expect} from 'vitest';
import {validateExecution} from '../src/feature-packs/code/execution';
import {validatePluginManifest,validatePluginSource} from '../src/plugins/loader';
import {validateTensors} from '../src/feature-packs/ml/contracts';
import {intersectionOverUnion,nonMaximumSuppression,yoloAdapter} from '../src/feature-packs/ml/yolo-adapter';
import {renderFormula} from '../src/feature-packs/math';
import {resourceURL} from '../src/feature-packs/three';
import {mapResource} from '../src/feature-packs/map';
import {readBounded} from '../src/feature-packs/fetch';

describe('bounded code execution contract',()=>{
 it('clamps wall time and output while preserving a valid language',()=>{expect(validateExecution({language:'javascript',code:'return 1',timeoutMs:Infinity,outputLimit:9999999})).toMatchObject({timeoutMs:5000,outputLimit:262144});expect(validateExecution({language:'python',code:'print(1)',timeoutMs:-4}).timeoutMs).toBe(100);});
 it('rejects unsupported languages and oversized source/input',()=>{expect(()=>validateExecution({language:'shell' as any,code:''})).toThrow();expect(()=>validateExecution({language:'javascript',code:'a'.repeat(65537)})).toThrow();expect(()=>validateExecution({language:'python',code:'',stdin:['a'.repeat(8193)]})).toThrow();});
});
describe('approved custom plugin boundary',()=>{
 const manifest={id:'teaching',version:'1.0.0',path:'plugins/teaching.js',sha256:'a'.repeat(64),capabilities:['functions']};
 it('requires explicit approval, identity, hash and declared supported capabilities',()=>{expect(validatePluginManifest(manifest,['teaching'],'https://localhost:41973/decks/test/').pathname).toBe('/decks/test/plugins/teaching.js');expect(()=>validatePluginManifest(manifest,[],'https://localhost:41973/')).toThrow(/approved/);expect(()=>validatePluginManifest({...manifest,sha256:'bad'},['teaching'],'https://localhost/')).toThrow();expect(()=>validatePluginManifest({...manifest,capabilities:['network']},['teaching'],'https://localhost/')).toThrow();});
 it('rejects remote and traversal paths even for approved plugins',()=>{for(const path of ['https://remote.test/module.js','../secrets.js','plugins/%2e%2e/evil.js','/evil.js'])expect(()=>validatePluginManifest({...manifest,path},['teaching'],'https://localhost/')).toThrow();});
 it('uses an ES parser to reject static/dynamic imports without rejecting comments and strings',async()=>{await expect(validatePluginSource('export default {text:"import x from x"}; // import("x")')).resolves.toBeUndefined();for(const source of ['import x from "x";export default x','export {x} from "x"','export default () => import("https://evil.test/x")','export default import.meta.url'])await expect(validatePluginSource(source)).rejects.toThrow(/self-contained/);});
});
describe('generic model contracts and separate YOLO adapter',()=>{
 it('checks shape/data agreement and finite tensor data',()=>{expect(validateTensors({x:{type:'float32',dims:[1,2],data:[1,2]}}).x.dims).toEqual([1,2]);expect(()=>validateTensors({x:{type:'float32',dims:[1,3],data:[1,2]}})).toThrow(/dimensions/);expect(()=>validateTensors({x:{type:'float32',dims:[1],data:[Infinity]}})).toThrow(/type/);expect(()=>validateTensors({x:{type:'float32',dims:[-1],data:[]}})).toThrow();});
 it('does not silently wrap out-of-range integer values',()=>{expect(()=>validateTensors({x:{type:'uint8',dims:[1],data:[256]}})).toThrow(/range/);expect(()=>validateTensors({x:{type:'int64',dims:[1],data:['9223372036854775808']}})).toThrow(/range/);expect(()=>validateTensors({x:{type:'float32',dims:[1],data:[1e100]}})).toThrow(/range/);});
 it('preprocesses RGBA to NCHW floats without changing core runtime',async()=>{const tensors=await yoloAdapter.preprocess({rgba:[255,128,0,255]},{width:1,height:1});expect(tensors.images.dims).toEqual([1,3,1,1]);expect(tensors.images.data).toEqual([1,128/255,0]);});
 it('applies class-aware NMS and decodes YOLO channel-major results',async()=>{expect(intersectionOverUnion([0,0,2,2],[1,1,3,3])).toBeCloseTo(1/7);const result=nonMaximumSuppression([{box:[0,0,10,10],score:.9,classId:0},{box:[1,1,11,11],score:.8,classId:0},{box:[1,1,11,11],score:.7,classId:1}],.5);expect(result).toHaveLength(2);const decoded=await yoloAdapter.postprocess({output:{type:'float32',dims:[1,5,1],data:[10,10,4,6,.9]}},{});expect(decoded[0]).toEqual({box:[8,7,12,13],score:.9,classId:0});});
});
describe('asset and math boundaries',()=>{
 it('cancels a chunked resource before accumulating beyond its budget',async()=>{let canceled=false;const response=new Response(new ReadableStream({start(controller){controller.enqueue(new Uint8Array(4));controller.enqueue(new Uint8Array(4));},cancel(){canceled=true;}}));await expect(readBounded(response,6)).rejects.toThrow(/exceeds/);expect(canceled).toBe(true);});
 it('allows local resources and explicit HTTPS origins only',()=>{expect(resourceURL('shape.bin','https://localhost/deck/',[])).toBe('https://localhost/deck/shape.bin');expect(mapResource('https://tiles.test/a','https://localhost/',['https://tiles.test'])).toBe('https://tiles.test/a');for(const url of ['https://evil.test/a','javascript:alert(1)','https://user:password@tiles.test/a']){expect(()=>mapResource(url,'https://localhost/',['https://tiles.test'])).toThrow();expect(()=>resourceURL(url,'https://localhost/',['https://tiles.test'])).toThrow();}});
 it('renders accessible math without trusting HTML commands',()=>{expect(renderFormula('x^2+1')).toContain('MathML');expect(renderFormula('\\href{javascript:alert(1)}{x}')).not.toContain('href="javascript:');expect(()=>renderFormula('x'.repeat(16385))).toThrow();});
});
