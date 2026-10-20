import {unzipSync,strFromU8} from 'fflate';
import type {CanvasSnapshot,Box} from './visual-edits';
export type NativeObjectInfo={id:string;page:number;name:string;kind:string;canText:boolean;canTransform:boolean;canDelete:boolean;canPaint:boolean;isLine:boolean;headEnd?:string;tailEnd?:string;frame?:Box;rotation:number;text:string;fontSize?:number;fontFace?:string;fontColor?:string;bold?:boolean;italic?:boolean;underline?:boolean;align?:string;valign?:string;fill?:string;lineColor?:string;lineWidth?:number;fillOpacity?:number;crop?:{l:number;t:number;r:number;b:number};cells?:{row:number;column:number;text:string;merged:boolean}[]};
const P='http://schemas.openxmlformats.org/presentationml/2006/main',A='http://schemas.openxmlformats.org/drawingml/2006/main';
const children=(n:Element,name:string)=>Array.from(n.children).filter(c=>c.localName===name);
const one=(n:Element|null|undefined,name:string)=>n?children(n,name)[0]:undefined;
const all=(n:Element,name:string)=>Array.from(n.getElementsByTagNameNS('*',name));
const xfrm=(n:Element)=>one(one(n,'spPr'),'xfrm')||one(n,'xfrm');
const string=(n:Element)=>children(n,'p').map(p=>all(p,'t').map(t=>t.textContent||'').join('')).join('\n');
const color=(n:Element|undefined)=>one(one(n,'solidFill'),'srgbClr')?.getAttribute('val')||undefined;
export function readNativeCanvas(bytes:Uint8Array,snapshot:CanvasSnapshot):Record<string,NativeObjectInfo>{
 let total=0,count=0;const wanted=new Set(snapshot.pages.map(p=>p.part));
 const parts=unzipSync(bytes,{filter:f=>{if(++count>10000||(total+=f.originalSize)>120*1024*1024)throw Error('PPTX is too large to inspect.');return wanted.has(f.name);}}),result:Record<string,NativeObjectInfo>={};
 for(const page of snapshot.pages){
  const data=parts[page.part];if(!data)throw Error('Missing slide XML.');const source=strFromU8(data);if(/<!DOCTYPE|<!ENTITY/i.test(source))throw Error('Unsupported XML declaration.');const doc=new DOMParser().parseFromString(source,'application/xml');if(doc.getElementsByTagName('parsererror').length)throw Error('Invalid slide XML.');
  const references=new Set(Array.from(doc.getElementsByTagName('*')).filter(n=>n.hasAttribute('spid')).map(n=>n.getAttribute('spid')));const connections=new Set([...all(doc.documentElement,'stCxn'),...all(doc.documentElement,'endCxn')].map(n=>n.getAttribute('id')));
  for(const object of page.objects){
   const props=Array.from(doc.getElementsByTagNameNS(P,'cNvPr')).filter(p=>p.getAttribute('id')===object.id);if(props.length!==1)continue;const node=props[0].parentElement?.parentElement;if(!node)continue;
   const xf=xfrm(node),off=one(xf,'off'),ext=one(xf,'ext');let frame:Box|undefined,axis=true;
   if(off&&ext){let x=Number(off.getAttribute('x')),y=Number(off.getAttribute('y')),w=Number(ext.getAttribute('cx')),h=Number(ext.getAttribute('cy'));for(let parent=node.parentElement;parent;parent=parent.parentElement){if(parent.localName!=='grpSp')continue;const pf=one(one(parent,'grpSpPr'),'xfrm'),po=one(pf,'off'),pe=one(pf,'ext'),pc=one(pf,'chOff'),pce=one(pf,'chExt');if(!pf||!po||!pe||!pc||!pce||Number(pf.getAttribute('rot'))%21600000||pf.getAttribute('flipH')==='1'||pf.getAttribute('flipV')==='1'){axis=false;break;}const sx=Number(pe.getAttribute('cx'))/Number(pce.getAttribute('cx')),sy=Number(pe.getAttribute('cy'))/Number(pce.getAttribute('cy'));x=Number(po.getAttribute('x'))+(x-Number(pc.getAttribute('x')))*sx;y=Number(po.getAttribute('y'))+(y-Number(pc.getAttribute('y')))*sy;w*=sx;h*=sy;}if(axis)frame={x:x/page.width,y:y/page.height,width:w/page.width,height:h/page.height};}
   const tx=one(node,'txBody'),text=tx?string(tx):'',canText=node.localName==='sp'&&!!tx&&!all(tx,'fld').length&&!all(tx,'oMath').length&&!all(tx,'oMathPara').length&&text.length<=3000;
   const runs=tx?all(tx,'rPr'):[],defaults=tx?all(tx,'defRPr'):[],rpr=runs[0]||defaults[0],ppr=tx?all(tx,'pPr')[0]:undefined,sp=one(node,'spPr'),line=one(sp,'ln'),crop=one(one(node,'blipFill'),'srcRect'),table=all(node,'tbl')[0];
   const info:NativeObjectInfo={id:object.id,page:page.number,name:object.name,kind:node.localName,canText,canTransform:!!frame&&axis&&node.localName!=='cxnSp'&&!connections.has(object.id),canDelete:node.localName!=='cxnSp'&&!connections.has(object.id)&&!references.has(object.id),canPaint:['sp','cxnSp'].includes(node.localName),isLine:node.localName==='cxnSp'||one(sp,'prstGeom')?.getAttribute('prst')==='line',frame,rotation:Number(xf?.getAttribute('rot')||0)/60000,text};
   if(rpr){const size=rpr.getAttribute('sz');if(size)info.fontSize=Number(size)/100;info.fontFace=one(rpr,'latin')?.getAttribute('typeface')||one(rpr,'ea')?.getAttribute('typeface')||undefined;info.fontColor=color(rpr);for(const k of ['bold','italic','underline'] as const){const attr=rpr.getAttribute(k==='bold'?'b':k==='italic'?'i':'u');if(attr!==null)info[k]=k==='underline'?attr!=='none':attr==='1';}}
   info.headEnd=one(line,'headEnd')?.getAttribute('type')||'none';info.tailEnd=one(line,'tailEnd')?.getAttribute('type')||'none';info.align=ppr?.getAttribute('algn')||undefined;info.valign=one(tx,'bodyPr')?.getAttribute('anchor')||undefined;info.fill=one(sp,'noFill')?'none':color(sp);info.lineColor=one(line,'noFill')?'none':color(line);if(line?.hasAttribute('w'))info.lineWidth=Number(line.getAttribute('w'))/12700;
   const alpha=one(one(one(sp,'solidFill'),'srgbClr'),'alpha');if(alpha)info.fillOpacity=Number(alpha.getAttribute('val'))/100000;
   if(node.localName==='pic')info.crop={l:Number(crop?.getAttribute('l')||0)/100000,t:Number(crop?.getAttribute('t')||0)/100000,r:Number(crop?.getAttribute('r')||0)/100000,b:Number(crop?.getAttribute('b')||0)/100000};
   if(table)info.cells=children(table,'tr').flatMap((row,i)=>children(row,'tc').map((cell,j)=>({row:i,column:j,text:one(cell,'txBody')?string(one(cell,'txBody')!):'',merged:cell.getAttribute('hMerge')==='1'||cell.getAttribute('vMerge')==='1'})));
   result[page.number+':'+object.id]=info;
  }
 }
 return result;
}
