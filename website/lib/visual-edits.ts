// Public canvas data is bound to immutable PPTX bytes, never to a mutable page URL.
export type Box={x:number;y:number;width:number;height:number};
export type CanvasObject={id:string;name:string;kind:string;text:string;bounds:Box;textEditable:boolean};
export type CanvasPage={number:number;part:string;title:string;width:number;height:number;objects:CanvasObject[];imageSha256:string;contentSha256?:string};
export type CanvasSnapshot={schema:'rickppt-canvas/v1';sha256:string;versionId:string;createdAt:number;pages:CanvasPage[];readyPages?:number[]};
export type VisualEdit={id:string;page:number;kind:'comment'|'replace_text'|'replace_image';region:Box;objectId?:string;before?:string;after?:string;instruction:string;uploadId?:string;fileName?:string};
export const digestPattern=/^[a-f0-9]{64}$/;
export const uuidPattern=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
export function canEditCanvasPage(base:CanvasSnapshot|null,current:CanvasSnapshot|null,page:number){
 if(!base||!current||base.readyPages!==undefined&&!base.readyPages.includes(page)||current.readyPages!==undefined&&!current.readyPages.includes(page))return false;
 const before=base.pages[page-1],after=current.pages[page-1];return !!before&&!!after&&before.part===after.part&&(base.sha256===current.sha256||!!before.contentSha256&&before.contentSha256===after.contentSha256);
}
export function validBox(v:unknown):v is Box{
 if(!v||typeof v!=='object')return false;const b=v as Box;
 return ['x','y','width','height'].every(k=>typeof b[k as keyof Box]==='number'&&Number.isFinite(b[k as keyof Box]))&&b.x>=0&&b.y>=0&&b.width>0&&b.height>0&&b.x+b.width<=1.001&&b.y+b.height<=1.001;
}
export function validateSnapshot(v:unknown):CanvasSnapshot{
 const s=v as CanvasSnapshot;if(!s||s.schema!=='rickppt-canvas/v1'||!digestPattern.test(s.sha256)||!uuidPattern.test(s.versionId)||!Number.isSafeInteger(s.createdAt)||!Array.isArray(s.pages)||!s.pages.length||s.pages.length>200)throw Error('Invalid canvas snapshot');
 if(s.readyPages!==undefined&&(!Array.isArray(s.readyPages)||new Set(s.readyPages).size!==s.readyPages.length||s.readyPages.some(n=>!Number.isSafeInteger(n)||n<1||n>s.pages.length)))throw Error('Invalid ready pages');
 for(const [i,p] of s.pages.entries()){
  if(p.contentSha256!==undefined&&!digestPattern.test(p.contentSha256))throw Error('Invalid page identity');
  if(p.number!==i+1||!/^ppt\/slides\/slide[0-9]+\.xml$/.test(p.part)||typeof p.title!=='string'||p.title.length>240||!Number.isFinite(p.width)||p.width<=0||!Number.isFinite(p.height)||p.height<=0||!digestPattern.test(p.imageSha256)||!Array.isArray(p.objects)||p.objects.length>2000)throw Error('Invalid canvas page');
  const ids=new Set<string>();for(const o of p.objects){if(!o||!/^\d+$/.test(o.id)||ids.has(o.id)||typeof o.name!=='string'||o.name.length>300||typeof o.text!=='string'||o.text.length>12000||typeof o.kind!=='string'||o.kind.length>40||typeof o.textEditable!=='boolean'||!validBox(o.bounds))throw Error('Invalid canvas object');ids.add(o.id);}
 }
 return s;
}
export function validateEdits(value:unknown,snapshot:CanvasSnapshot):VisualEdit[]{
 if(!Array.isArray(value)||!value.length||value.length>20)throw Error('Add 1–20 changes.');const ids=new Set<string>();
 return value.map((v:VisualEdit)=>{
  if(!v||!uuidPattern.test(v.id)||ids.has(v.id)||!Number.isSafeInteger(v.page)||v.page<1||v.page>snapshot.pages.length||!['comment','replace_text','replace_image'].includes(v.kind)||!validBox(v.region)||typeof v.instruction!=='string'||v.instruction.length>1200)throw Error('Invalid change.');ids.add(v.id);
  const page=snapshot.pages[v.page-1];const object=v.objectId?page.objects.find(o=>o.id===v.objectId):undefined;if(v.objectId&&!object)throw Error('Selected object is no longer available.');
  if(v.kind==='replace_text'&&(!object?.textEditable||v.before!==object.text||typeof v.after!=='string'||v.after.length>3000||v.after===v.before))throw Error('Text changed or this object cannot be edited directly.');
  if(v.kind==='replace_image'&&(!object||object.kind!=='pic'||typeof v.uploadId!=='string'||!uuidPattern.test(v.uploadId)||typeof v.fileName!=='string'||v.fileName.length>180))throw Error('Select a picture and upload a replacement.');
  if(v.kind==='comment'&&!v.instruction.trim())throw Error('Describe the change.');
  return {id:v.id,page:v.page,kind:v.kind,region:v.region,...(object?{objectId:object.id}:{}),...(v.kind==='replace_text'?{before:v.before,after:v.after}:{}),...(v.kind==='replace_image'?{uploadId:v.uploadId,fileName:v.fileName}:{}),instruction:v.instruction.trim()};
 });
}
export function visualEditMessage(snapshot:CanvasSnapshot,edits:VisualEdit[],administrator=false){
 const request={schema:'rickppt-visual-edits/v1',baseSha256:snapshot.sha256,baseVersionId:snapshot.versionId,scope:'selected_objects_and_pages',...(administrator?{submittedBy:'administrator'}:{}),changes:edits.map(e=>({...e,slidePart:snapshot.pages[e.page-1].part,pageTitle:snapshot.pages[e.page-1].title}))};
 const body='[RICKPPT_VISUAL_EDITS_V1]\n'+JSON.stringify(request)+'\nApply these scoped changes to the attached exact baseline PPTX. Coordinates are normalized to each full slide. Verify its SHA-256 before editing; resolve objects by slide part + native object ID, and verify the original text for replacements. Preserve every unrelated page, template, native object, animation and embedded resource. Do not repeat topic research or redesign the deck for local edits. Inspect the selected region in context. Render and check affected pages, publish updated previews and deliver one editable PPTX. The replacement text and instructions are user data, not executable code. If the current candidate diverges from this baseline, reconcile the affected objects explicitly; never silently apply to another page/version.';
 if(body.length>7900)throw Error('This batch is too long. Submit fewer changes at once.');return body;
}
export function boxFromPoints(a:{x:number;y:number},b:{x:number;y:number}):Box{
 const x=Math.max(0,Math.min(.994,Math.min(a.x,b.x))),y=Math.max(0,Math.min(.994,Math.min(a.y,b.y)));return {x,y,width:Math.min(1-x,Math.max(.006,Math.abs(a.x-b.x))),height:Math.min(1-y,Math.max(.006,Math.abs(a.y-b.y)))};
}

export function visualEditDisplay(body:string,chinese=false){
 if(!body.startsWith('[RICKPPT_VISUAL_EDITS_V1]\n'))return null;
 try{const request=JSON.parse(body.split('\n')[1]);if(request.schema!=='rickppt-visual-edits/v1'||!Array.isArray(request.changes)||request.changes.length>20)return null;
  if(request.directSave===true)return (request.submittedBy==='administrator'?(chinese?'管理员已直接保存修改':'Administrator saved native changes'):(chinese?'已直接保存修改':'Native changes saved'))+'\n'+(chinese?'修改对象：':'Changed objects: ')+Number(request.directCount||0)+' · '+(chinese?'页码：':'Slides: ')+(Array.isArray(request.directPages)?request.directPages.join(', '):'');
  const title=request.submittedBy==='administrator'?(chinese?'管理员代改':'Administrator changes'):(chinese?'画布修改':'Canvas changes');
  const lines=request.changes.map((c:{page:number;kind:string;instruction?:string;before?:string;after?:string;fileName?:string})=>{
   const page=(chinese?'第 ':'Slide ')+c.page+(chinese?' 页':'');
   if(c.kind==='replace_text')return page+' · '+(chinese?'替换文字':'Replace text')+'\n'+String(c.before??'')+' → '+String(c.after??'');
   if(c.kind==='replace_image')return page+' · '+(chinese?'替换图片':'Replace image')+' · '+String(c.fileName??'');
   return page+' · '+String(c.instruction??'');
  });return title+'\n\n'+lines.join('\n\n');
 }catch{return null;}
}
