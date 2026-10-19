'use client';
import {useId} from 'react';
export type DiagramObject={id:string;x:number;y:number;width:number;height:number;label:string;fill:string;stage:number};
export const diagramObjects:DiagramObject[]=[
 {id:'input-embedding',x:115,y:548,width:106,height:32,label:'Input\nEmbedding',fill:'#efdbd5',stage:0},
 {id:'output-embedding',x:352,y:548,width:106,height:32,label:'Output\nEmbedding',fill:'#efdbd5',stage:0},
 {id:'encoder-attention',x:115,y:449,width:106,height:35,label:'Multi-Head\nAttention',fill:'#f1dfbd',stage:1},
 {id:'encoder-norm-1',x:115,y:411,width:106,height:23,label:'Add & Norm',fill:'#e8e6c6',stage:1},
 {id:'encoder-ff',x:115,y:359,width:106,height:35,label:'Feed\nForward',fill:'#d2e4e9',stage:1},
 {id:'encoder-norm-2',x:115,y:321,width:106,height:23,label:'Add & Norm',fill:'#e8e6c6',stage:1},
 {id:'decoder-masked',x:352,y:449,width:106,height:35,label:'Masked\nMulti-Head\nAttention',fill:'#f1dfbd',stage:2},
 {id:'decoder-norm-1',x:352,y:411,width:106,height:23,label:'Add & Norm',fill:'#e8e6c6',stage:2},
 {id:'decoder-cross',x:352,y:359,width:106,height:35,label:'Multi-Head\nAttention',fill:'#f1dfbd',stage:3},
 {id:'decoder-norm-2',x:352,y:321,width:106,height:23,label:'Add & Norm',fill:'#e8e6c6',stage:3},
 {id:'decoder-ff',x:352,y:269,width:106,height:35,label:'Feed\nForward',fill:'#d2e4e9',stage:4},
 {id:'decoder-norm-3',x:352,y:231,width:106,height:23,label:'Add & Norm',fill:'#e8e6c6',stage:4},
 {id:'linear',x:352,y:186,width:106,height:25,label:'Linear',fill:'#ddd9e9',stage:4},
 {id:'softmax',x:352,y:141,width:106,height:25,label:'Softmax',fill:'#d3e7d6',stage:4}
];
type Props={compact?:boolean;stage?:number;monochrome?:boolean;selected?:string;overrides?:Record<string,{label?:string;fill?:string}>;onSelect?:(id:string)=>void;label:string;interactiveLabel?:string};
export default function TransformerDiagram({compact=false,stage=4,monochrome=false,selected,overrides={},onSelect,label,interactiveLabel}:Props){
 const marker=useId().replace(/:/g,'')+'arrow';
 const line=(d:string,key?:string)=><path key={key??d} d={d} fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinejoin="round" markerEnd={`url(#${marker})`}/>;
 const visible=(n:number)=>({opacity:n<=stage?1:0,pointerEvents:n<=stage?'auto' as const:'none' as const});
 return <svg className={`transformer-diagram${monochrome?' is-linework':''}`} viewBox={compact?"35 44 500 598":"0 0 570 650"} role={onSelect?'group':'img'} aria-label={label}>
 <title>{label}</title><desc>Encoder on the left, decoder on the right. Both use post-normalization residual connections. The encoder output supplies keys and values to decoder cross-attention.</desc>
 <defs><marker id={marker} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M1 1 L7 4 L1 7 Z" fill="currentColor"/></marker></defs>
 <g className="diagram-context"><text x="168" y="60" textAnchor="middle" className="diagram-column">ENCODER</text><text x="405" y="60" textAnchor="middle" className="diagram-column">DECODER</text>
 <rect x="82" y="310" width="177" height="193" rx="12" className="diagram-stack"/><rect x="319" y="220" width="177" height="283" rx="12" className="diagram-stack"/>
 <text x="60" y="410" className="diagram-repeat">N×</text><text x="506" y="365" className="diagram-repeat">N×</text>
 {[168,405].map(x=>{const pe=x===168?x-48:x+48;const labelX=x===168?68:512;return <g key={x}>{line(`M${x} 602 V580`)}{line(`M${x} 548 V537`)}<circle cx={x} cy="529" r="8" fill="#fffefa" stroke="currentColor" strokeWidth="1.1"/><path d={`M${x-4} 529 H${x+4} M${x} 525 V533`} fill="none" stroke="currentColor" strokeWidth="1"/>
 <circle cx={pe} cy="529" r="10" fill="#fffefa" stroke="currentColor" strokeWidth="1"/><path d={`M${pe-8} 529 Q${pe-4} 515 ${pe} 529 T${pe+8} 529`} fill="none" stroke="currentColor" strokeWidth="1"/>{line(x===168?`M${pe+10} 529 H${x-8}`:`M${pe-10} 529 H${x+8}`)}<text x={labelX} y="526" textAnchor="middle" className="diagram-tiny"><tspan x={labelX}>Positional</tspan><tspan x={labelX} dy="12">Encoding</tspan></text></g>})}
 <text x="168" y="622" textAnchor="middle">Inputs</text><text x="405" y="618" textAnchor="middle"><tspan x="405">Outputs</tspan><tspan x="405" dy="15">(shifted right)</tspan></text></g>
 <g className="diagram-build" style={visible(1)}>
 {line('M168 521 V494 H143 V484')}{line('M168 494 V484')}{line('M168 494 H193 V484')}{line('M168 449 V434')}{line('M168 411 V394')}{line('M168 359 V344')}
 {line('M168 494 H97 V422 H115')}{line('M168 404 H97 V332 H115')}
 </g>
 <g className="diagram-build" style={visible(2)}>{line('M405 521 V494 H380 V484')}{line('M405 494 V484')}{line('M405 494 H430 V484')}{line('M405 449 V434')}{line('M405 494 H480 V422 H458')}</g>
 <g className="diagram-build diagram-cross" style={visible(3)}>{line('M168 321 V297 H286 V405 H380 V394')}{line('M286 405 H405 V394')}{line('M405 411 V402 H430 V394')}{line('M405 359 V344')}{line('M405 404 H480 V332 H458')}</g>
 <g className="diagram-build" style={visible(4)}>{line('M405 321 V304')}{line('M405 269 V254')}{line('M405 315 H480 V242 H458')}{line('M405 231 V211')}{line('M405 186 V166')}{line('M405 141 V113')}<text x="405" y="87" textAnchor="middle"><tspan x="405">Output</tspan><tspan x="405" dy="14">Probabilities</tspan></text></g>
 {diagramObjects.map(obj=>{const isSelected=selected===obj.id;const text=overrides[obj.id]?.label??obj.label;const lines=text.includes('\n')?text.split('\n'):(text.match(/.{1,17}(?:\s|$)|.{1,17}/gu)??['']).map(line=>line.trim());const fontSize=Math.min(11,(obj.height-4)/(Math.max(1,lines.length)*1.1),(obj.width-12)/Math.max(1,...lines.map(line=>Array.from(line).reduce((n,ch)=>n+(/[^\x00-\xff]/.test(ch)?1:.56),0))));const lineHeight=Math.min(12,fontSize*1.1);return <g key={obj.id} className={`diagram-build diagram-object${onSelect?' is-interactive':''}${isSelected?' is-selected':''}`} style={visible(obj.stage)} {...(onSelect?{role:'button',tabIndex:obj.stage<=stage?0:-1,'aria-label':`${interactiveLabel??'Select'}: ${(text||obj.label).replaceAll('\n',' ')}`,'aria-pressed':isSelected,onClick:()=>onSelect(obj.id),onKeyDown:(e:React.KeyboardEvent)=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(obj.id);}}}:{})}>
 <rect x={obj.x} y={obj.y} width={obj.width} height={obj.height} rx="3" fill={monochrome?'#fffefa':overrides[obj.id]?.fill??obj.fill} stroke="currentColor" strokeWidth="1.15"/>
 <text x={obj.x+obj.width/2} y={obj.y+obj.height/2-(lines.length-1)*lineHeight/2+fontSize*.34} textAnchor="middle" className="diagram-object-text" style={{fontSize}}>{lines.map((text,index)=><tspan key={index} x={obj.x+obj.width/2} dy={index===0?0:lineHeight}>{text}</tspan>)}</text>
 {isSelected&&<g className="selection-handles"><rect x={obj.x-5} y={obj.y-5} width={obj.width+10} height={obj.height+10} fill="none" stroke="#498274" strokeWidth="1.2"/>{[[obj.x-5,obj.y-5],[obj.x+obj.width+5,obj.y-5],[obj.x-5,obj.y+obj.height+5],[obj.x+obj.width+5,obj.y+obj.height+5]].map(([x,y])=><rect key={`${x}-${y}`} x={x-2.5} y={y-2.5} width="5" height="5" fill="white" stroke="#498274"/>)}</g>}
 </g>})}
 </svg>;
}
