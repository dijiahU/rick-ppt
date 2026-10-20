import {type Box,type CanvasSnapshot,validBox,uuidPattern} from './visual-edits';
export type NativePatch={page:number;objectId:string;text?:string;fontFace?:string;fontSize?:number;bold?:boolean;italic?:boolean;underline?:boolean;fontColor?:string;align?:'l'|'ctr'|'r'|'just';valign?:'t'|'ctr'|'b';box?:Box;rotation?:number;fill?:string;lineColor?:string;lineWidth?:number;headEnd?:string;tailEnd?:string;fillOpacity?:number;layer?:'front'|'back'|'forward'|'backward';delete?:boolean;crop?:{l:number;t:number;r:number;b:number};image?:{id:string;uploadId:string;fileName:string};cells?:{row:number;column:number;text:string}[];background?:string};
const color=(v:unknown)=>typeof v==='string'&&/^[0-9A-Fa-f]{6}$/.test(v);
export function validateNativePatches(input:unknown,snapshot:CanvasSnapshot):NativePatch[]{
 if(!Array.isArray(input)||!input.length||input.length>100)throw Error('Save 1–100 object changes at a time.');
 const keys=new Set(['page','objectId','text','fontFace','fontSize','bold','italic','underline','fontColor','align','valign','box','rotation','fill','lineColor','lineWidth','headEnd','tailEnd','fillOpacity','layer','delete','crop','image','cells','background']),seen=new Set<string>();
 return input.map((v:NativePatch)=>{
  if(!v||typeof v!=='object'||Object.keys(v).some(k=>!keys.has(k))||!Number.isSafeInteger(v.page)||!snapshot.pages[v.page-1]||typeof v.objectId!=='string'||Object.keys(v).length<3)throw Error('Invalid native change.');
  const key=v.page+':'+v.objectId;if(seen.has(key))throw Error('Duplicate object change.');seen.add(key);
  if(v.objectId==='page'){if(Object.keys(v).some(k=>!['page','objectId','background'].includes(k))||!color(v.background))throw Error('Invalid slide background.');return v;}
  const object=snapshot.pages[v.page-1].objects.find(o=>o.id===v.objectId);if(!object)throw Error('Object is unavailable in this version.');
  if(v.text!==undefined&&(object.kind!=='sp'||typeof v.text!=='string'||v.text.length>3000))throw Error('Use a comment for this complex text object.');
  for(const k of ['fontColor','background'] as const)if(v[k]!==undefined&&!color(v[k]))throw Error('Invalid color.');
  for(const k of ['fill','lineColor'] as const)if(v[k]!==undefined&&v[k]!=='none'&&!color(v[k]))throw Error('Invalid color.');
  if(v.fontFace!==undefined&&!['Times New Roman','SimSun'].includes(v.fontFace))throw Error('Select an available cross-platform font.');
  for(const [k,min,max] of [['fontSize',1,400],['rotation',-360,360],['lineWidth',0,40],['fillOpacity',0,1]] as const)if(v[k]!==undefined&&(typeof v[k]!=='number'||!Number.isFinite(v[k])||v[k]!<min||v[k]!>max))throw Error('Invalid '+k+'.');
  for(const k of ['bold','italic','underline','delete'] as const)if(v[k]!==undefined&&typeof v[k]!=='boolean')throw Error('Invalid '+k+'.');
  for(const k of ['headEnd','tailEnd'] as const)if(v[k]!==undefined&&!['none','triangle','stealth','diamond','oval','arrow'].includes(v[k]!))throw Error('Invalid arrow ending.');
  if(v.box!==undefined&&!validBox(v.box))throw Error('Keep the object within the slide.');
  if(v.align!==undefined&&!['l','ctr','r','just'].includes(v.align)||v.valign!==undefined&&!['t','ctr','b'].includes(v.valign)||v.layer!==undefined&&!['front','back','forward','backward'].includes(v.layer))throw Error('Invalid alignment or layer.');
  if(v.crop!==undefined&&(object.kind!=='pic'||!['l','t','r','b'].every(k=>typeof v.crop![k as keyof typeof v.crop]==='number'&&Number.isFinite(v.crop![k as keyof typeof v.crop])&&v.crop![k as keyof typeof v.crop]>=0)||v.crop.l+v.crop.r>=.98||v.crop.t+v.crop.b>=.98))throw Error('Invalid picture crop.');
  if(v.image!==undefined&&(object.kind!=='pic'||!uuidPattern.test(v.image.id)||!uuidPattern.test(v.image.uploadId)||typeof v.image.fileName!=='string'||v.image.fileName.length>180))throw Error('Invalid replacement picture.');
  if(v.cells!==undefined&&(object.kind!=='graphicFrame'||!Array.isArray(v.cells)||!v.cells.length||v.cells.length>400||v.cells.some(c=>!Number.isSafeInteger(c.row)||!Number.isSafeInteger(c.column)||c.row<0||c.column<0||typeof c.text!=='string'||c.text.length>3000)))throw Error('Invalid table changes.');
  if(v.delete&&Object.keys(v).some(k=>!['page','objectId','delete'].includes(k)))throw Error('Remove other changes before deleting this object.');
  return v;
 });
}
