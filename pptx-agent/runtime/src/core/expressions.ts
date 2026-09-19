import jsep from 'jsep';
import {forbidden,safeKey} from './state';
import type {Environment} from './types';
export class FunctionRegistry {
 private functions=new Map<string,(...args:any[])=>any>();
 register(name:string,fn:(...args:any[])=>any){if(!/^[A-Za-z][\w]*$/.test(name)||forbidden.has(name)||this.functions.has(name))throw new Error(`Invalid/duplicate function ${name}`);this.functions.set(name,fn);}
 call(name:string,args:any[]){const fn=this.functions.get(name);if(!fn)throw new Error(`Unknown function: ${name}`);return fn(...args);}
 has(name:string){return this.functions.has(name);}
}
const list=(a:any[])=>a.length===1&&Array.isArray(a[0])?a[0]:a;
export function builtinFunctions(){const r=new FunctionRegistry();const f:Record<string,(...a:any[])=>any>={
 min:(...a)=>Math.min(...list(a)),max:(...a)=>Math.max(...list(a)),sum:(a)=>a.reduce((s:number,v:any)=>s+Number(v),0),mean:(a)=>a.length?a.reduce((s:number,v:any)=>s+Number(v),0)/a.length:0,
 clamp:(v,a,b)=>Math.max(a,Math.min(b,v)),lerp:(a,b,t)=>a+(b-a)*t,format:(v,d=2)=>typeof v==='number'?v.toFixed(Math.max(0,Math.min(12,d))):String(v),length:(a)=>a?.length??0,
 range:(n,start=0,step=1)=>Array.from({length:Math.max(0,Math.min(10000,Math.floor(n)))},(_,i)=>start+i*step),at:(a,i)=>a?.[Math.floor(i)],concat:(...a)=>a.flat(),slice:(a,s,e)=>a.slice(s,e),join:(a,s=', ')=>a.join(s),
 upper:(s)=>String(s).toUpperCase(),lower:(s)=>String(s).toLowerCase(),abs:Math.abs,round:Math.round,floor:Math.floor,ceil:Math.ceil,sqrt:Math.sqrt,pow:Math.pow,exp:Math.exp,log:Math.log,sin:Math.sin,cos:Math.cos,tan:Math.tan,atan2:Math.atan2,
 distance:(x,y,a,b)=>Math.hypot(x-a,y-b),rgb:(r,g,b)=>`rgb(${[r,g,b].map(x=>Math.round(Math.max(0,Math.min(255,x)))).join(',')})`,hex:(v)=>'#'+Math.max(0,Math.min(0xffffff,v)).toString(16).padStart(6,'0'),
 dot:(a,b)=>a.reduce((s:number,v:number,i:number)=>s+v*(b[i]??0),0),flatten:(a)=>a.flat(),pluck:(a,k)=>{safeKey(k);return a.map((v:any)=>Object.hasOwn(v,k)?v[k]:null);},sort:(a)=>[...a].sort((a,b)=>a-b),includes:(a,v)=>a.includes(v),coalesce:(a,b)=>a??b,
 rgba:(r,g,b,a)=>`rgba(${r},${g},${b},${a})`,replace:(s,a,b)=>String(s).split(a).join(b)};
 for(const [name,fn]of Object.entries(f))r.register(name,fn);return r;}
export class Expressions {
 private cache=new Map<string,jsep.Expression>();private depth=0;
 constructor(public functions=builtinFunctions()){}
 evaluate(source:string,env:Environment):any {if(source.length>2048)throw new Error('Expression too long');if(++this.depth>32){this.depth--;throw new Error('Function recursion limit');}try{let ast=this.cache.get(source);if(!ast){ast=jsep(source);if(this.cache.size>2048)this.cache.clear();this.cache.set(source,ast);}let budget=4096;
 const read=(n:any):any=>{if(--budget<0)throw new Error('Expression budget exceeded');switch(n.type){
 case 'Literal':return n.value;
 case 'Identifier':{safeKey(n.name);if(['state','data','locals','event'].includes(n.name))return (env as any)[n.name]??{};if(n.name==='PI')return Math.PI;if(n.name==='E')return Math.E;if(Object.hasOwn(env.locals??{},n.name))return env.locals![n.name];throw new Error(`Unknown identifier: ${n.name}`);}
 case 'ArrayExpression':return n.elements.map(read);
 case 'MemberExpression':{const o=read(n.object);const k=String(n.computed?read(n.property):n.property.name);safeKey(k);if(o==null)return undefined;if(typeof o==='string'&&k==='length')return o.length;return Object.hasOwn(Object(o),k)?o[k]:undefined;}
 case 'UnaryExpression':{const v=read(n.argument);if(n.operator==='!')return !v;if(n.operator==='-')return -v;if(n.operator==='+')return +v;throw new Error('Unsupported unary operator');}
 case 'BinaryExpression':case 'LogicalExpression':{const a=read(n.left);if(n.operator==='&&')return a&&read(n.right);if(n.operator==='||')return a||read(n.right);if(n.operator==='??')return a??read(n.right);const b=read(n.right);switch(n.operator){case '+':return a+b;case '-':return a-b;case '*':return a*b;case '/':return a/b;case '%':return a%b;case '**':return a**b;case '<':return a<b;case '>':return a>b;case '<=':return a<=b;case '>=':return a>=b;case '==':case '===':return a===b;case '!=':case '!==':return a!==b;default:throw new Error('Unsupported operator');}}
 case 'ConditionalExpression':return read(n.test)?read(n.consequent):read(n.alternate);
 case 'CallExpression':{let name=n.callee.name;if(n.callee.type==='MemberExpression'&&n.callee.object.name==='Math'&&!n.callee.computed)name=n.callee.property.name;else if(n.callee.type!=='Identifier')throw new Error('Only registered function calls allowed');safeKey(name);return this.functions.call(name,n.arguments.map(read));}
 default:throw new Error(`Unsupported expression: ${n.type}`);}};return read(ast);}finally{this.depth--;}}
 value(value:any,env:Environment):any{if(value&&typeof value==='object'){if(Object.keys(value).length===1&&typeof value.expr==='string')return this.evaluate(value.expr,env);if(Array.isArray(value))return value.map(v=>this.value(v,env));return Object.fromEntries(Object.entries(value).map(([k,v])=>[safeKey(k),this.value(v,env)]));}return value;}
}
