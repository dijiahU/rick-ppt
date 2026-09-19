import {useMemo} from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import type {FeaturePack,FeatureProps} from '../types';
export function renderFormula(tex:string,displayMode=false){if(tex.length>16384)throw new Error('Formula exceeds 16 KiB');return katex.renderToString(tex,{displayMode,throwOnError:false,trust:false,strict:'warn',maxExpand:1000,maxSize:20,output:'htmlAndMathml'});}
export function MathFormula({p}:FeatureProps){const html=useMemo(()=>renderFormula(String(p.tex??p.value??''),!!p.displayMode),[p.tex,p.value,p.displayMode]);return <div role="math" aria-label={p.ariaLabel??p.tex} style={{fontSize:p.fontSize??28,padding:p.padding??8,color:p.color??'#172033',overflow:'auto',height:'100%',boxSizing:'border-box'}} dangerouslySetInnerHTML={{__html:html}}/>;}
const pack:FeaturePack={id:'math',install(context){context.component('Math',MathFormula);context.component('Formula',MathFormula);}};export default pack;
