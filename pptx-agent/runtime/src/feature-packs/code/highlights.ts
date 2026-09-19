export type HighlightRange={startLineNumber:number;endLineNumber:number};

/** Declarative 1-based lines, or an array of lines / inclusive [start,end] pairs. */
export function normalizeHighlightLines(value:unknown,lineCount:number):HighlightRange[]{
 if(!Number.isSafeInteger(lineCount)||lineCount<1)return [];
 const entries=typeof value==='number'?[value]:Array.isArray(value)?value.slice(0,128):[];
 const ranges:HighlightRange[]=[];
 for(const entry of entries){
  const pair=typeof entry==='number'?[entry,entry]:Array.isArray(entry)&&entry.length===2?entry:[];
  const [start,end]=pair;
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<1||end<start||end>lineCount)continue;
  ranges.push({startLineNumber:start,endLineNumber:end});
 }
 ranges.sort((a,b)=>a.startLineNumber-b.startLineNumber||a.endLineNumber-b.endLineNumber);
 const result:HighlightRange[]=[];
 for(const range of ranges){
  const last=result[result.length-1];
  if(last&&range.startLineNumber<=last.endLineNumber+1)last.endLineNumber=Math.max(last.endLineNumber,range.endLineNumber);
  else result.push({...range});
 }
 return result;
}
