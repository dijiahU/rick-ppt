'use client';
import {useEffect,useState} from 'react';
import {useLanguage} from '@/app/language';
import type {UsageRecord} from '@/lib/usage';
type Group={source:'api'|'codex';provider:string;model:string;stage:string;calls:number;reportedCalls:number;unpricedCalls:number;inputTokens:number|null;cachedInputTokens:number|null;cacheWriteTokens:number|null;outputTokens:number|null;reasoningTokens:number|null;totalTokens:number|null;costMicrousd:number|null};
type Data={available:boolean;groups:Group[];records:UsageRecord[];total:number;nextOffset:number;chargingEnabled:false};
export default function UsagePanel({id}:{id:string}){
 const {locale}=useLanguage(),zh=locale==='zh-CN';
 const [data,setData]=useState<Data|null>(null),[error,setError]=useState(false);
 useEffect(()=>{let active=true;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  async function poll(){try{const response=await fetch(`/api/admin/jobs/${id}/usage`,{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();const value=await response.json() as Data;if(active){setData(value);setError(false);}}catch{if(active)setError(true);}finally{if(active)timer=setTimeout(poll,5000);}}
  void poll();return()=>{active=false;controller.abort();clearTimeout(timer);};
 },[id]);
 const num=(n:number|null)=>n===null?'—':n.toLocaleString(locale);
 const money=(n:number|null)=>n===null?'—':new Intl.NumberFormat(locale,{style:'currency',currency:'USD',minimumFractionDigits:6,maximumFractionDigits:6}).format(n/1000000);
 const api=data?.groups.filter(g=>g.source==='api')??[],local=data?.groups.filter(g=>g.source==='codex')??[];
 const unpriced=api.reduce((n,g)=>n+g.unpricedCalls,0),knownCost=api.reduce((n,g)=>n+(g.costMicrousd??0),0),hasPrice=api.some(g=>g.costMicrousd!==null);
 const summary=(groups:Group[])=>groups.reduce((n,g)=>n+(g.totalTokens??0),0);
 return <section className="admin-usage" aria-label={zh?'内部用量账本':'Internal usage ledger'}>
  <h3>{zh?'内部用量账本':'Internal usage ledger'}</h3>
  <p className="fineprint">{zh?'仅管理员可见 · 仅记录成本，不扣款':'Administrator only · Cost recording, no charges'}</p>
  {error&&<p role="alert">{zh?'用量暂时无法刷新，已有数据可能过期。':'Unable to refresh usage. Displayed records may be out of date.'}</p>}
  {!data?<p>{zh?'正在读取…':'Loading…'}</p>:!data.available?<p>{zh?'暂无用量记录。历史任务不补造数据。':'No usage receipts. Historical usage is not fabricated.'}</p>:<>
   <dl><dt>{zh?'已报告 API token':'Reported API tokens'}</dt><dd>{api.some(g=>g.reportedCalls>0)?num(summary(api)):'—'}</dd><dt>{zh?'本地 Codex token':'Local Codex tokens'}</dt><dd>{local.some(g=>g.reportedCalls>0)?num(summary(local)):'—'}</dd><dt>{zh?'已核价 API 小计':'Priced API subtotal'}</dt><dd>{money(hasPrice?knownCost:null)}</dd><dt>{zh?'待核价调用':'Unpriced API calls'}</dt><dd>{num(unpriced)}</dd></dl>
   <p className="fineprint">{zh?'用量取自 API 或执行端回执；缺失数据不按 0 处理。本地用量不冒充 API 账单。费用只核算已配置单价的模型 token，搜索、生图等额外费用尚未计入。':'Usage comes from API or host receipts. Missing usage is not zero. Local usage is separate from API billing. Costs cover model tokens with configured rates; additional search/image fees are not included.'}</p>
   <div className="admin-table-wrap"><table><thead><tr><th>{zh?'来源 / 模型 / 阶段':'Source / model / stage'}</th><th>{zh?'输入 / 缓存读取 / 缓存写入':'Input / cached / cache write'}</th><th>{zh?'输出 / 其中推理':'Output / reasoning subset'}</th><th>{zh?'回执 / 调用':'Reported / calls'}</th><th>{zh?'核算 USD':'Calculated USD'}</th></tr></thead><tbody>{data.groups.map(g=><tr key={[g.source,g.provider,g.model,g.stage].join(':')}><td>{g.source==='api'?'API':'Codex'}<small>{g.provider}</small><small>{g.model}</small><small>{g.stage}</small></td><td>{num(g.inputTokens)}<small>{num(g.cachedInputTokens)} / {num(g.cacheWriteTokens)}</small></td><td>{num(g.outputTokens)}<small>{num(g.reasoningTokens)}</small></td><td>{g.reportedCalls} / {g.calls}</td><td>{g.source==='codex'?'—':money(g.costMicrousd)}{g.unpricedCalls>0&&<small>{zh?'部分待核价':'Partly unpriced'}</small>}</td></tr>)}</tbody></table></div>
   <details><summary>{zh?'查看逐次回执':'View individual receipts'} · {Math.min(data.total,100)} / {data.total}</summary><pre>{JSON.stringify(data.records,null,2)}</pre></details>
  </>}
 </section>;
}
