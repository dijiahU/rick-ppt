import config from '../../config.json';
declare const Office:any;
export type Identity={deckId:string;sceneId:string;instanceId:string;schemaVersion:number;specHash:string};
export async function identity():Promise<Identity|null>{
 if(!location.pathname.endsWith('content.html'))return null;
 if(typeof Office==='undefined')throw new Error('Office.js is unavailable');
 await Office.onReady();
 if(Office.context.host!=='PowerPoint')throw new Error('PowerPoint is required');
 const settings=Office.context.document.settings,result={} as Identity;
 // Office Settings already deserializes the OOXML property values. Parsing a
 // string again would turn valid names such as "null" or "false" into values.
 for(const key of ['deckId','sceneId','instanceId','specHash'] as const){
  const value:unknown=settings.get(key);
  if(typeof value!=='string'||!value.trim())throw new Error(`Invalid content identity ${key}: expected a nonempty string.`);
  result[key]=value;
 }
 const version:unknown=settings.get('schemaVersion');
 if(typeof version!=='number'||!Number.isInteger(version)||version!==config.schemaVersion)throw new Error(`Invalid content identity schemaVersion: expected number ${config.schemaVersion}.`);
 result.schemaVersion=version;
 return result;
}
export async function saveIdentity(value:Identity){for(const [k,v]of Object.entries(value))Office.context.document.settings.set(k,v);return new Promise<void>((resolve,reject)=>Office.context.document.settings.saveAsync((r:any)=>r.status==='succeeded'?resolve():reject(new Error(r.error?.message??'Settings persistence failed'))));}
export function capabilities(){return{office:typeof Office!=='undefined',powerPointApi:typeof Office!=='undefined'&&Office.context?.requirements?.isSetSupported('PowerPointApi','1.1'),webGPU:'gpu'in navigator,webAssembly:typeof WebAssembly!=='undefined',webGL2:!!document.createElement('canvas').getContext('webgl2'),worker:typeof Worker!=='undefined',offscreenCanvas:typeof OffscreenCanvas!=='undefined',audio:typeof Audio!=='undefined',video:!!document.createElement('video').canPlayType,addinId:config.addinId};}
