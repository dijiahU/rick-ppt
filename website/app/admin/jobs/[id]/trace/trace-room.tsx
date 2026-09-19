'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import type {TraceEvent} from '@/lib/admin-trace';
type Snapshot={available:boolean;events:TraceEvent[];nextChunk:number;totalEvents:number;totalChunks:number;status:string;attempt:string|null;updatedAt?:number;finished?:boolean};
const labels:Record<string,string>={phase:'阶段',command:'命令',tool:'工具',search:'搜索与来源',file:'文件修改',media:'图片与素材',note:'工作说明',review:'审核结果',error:'错误'};
const stageNames:Record<string,string>={setup:'准备',research:'研究与内容',author:'制作页面',verification:'成品校验',attachments:'读取附件',delivery:'上传交付',finished:'执行结束'};
function stageName(value:string){if(stageNames[value])return stageNames[value];if(value.startsWith('content-first'))return '内容审核 · 首次观看';if(value.startsWith('content-evidence'))return '内容审核 · 核对资料';if(value.startsWith('visual'))return '视觉审核';if(value.startsWith('content-revision'))return '内容修改';if(value.startsWith('repair'))return '页面修改';return value;}
export default function TraceRoom({id}:{id:string}){
 const [events,setEvents]=useState<TraceEvent[]>([]),[snapshot,setSnapshot]=useState<Snapshot|null>(null),[error,setError]=useState(''),[title,setTitle]=useState('任务执行记录');
 const [kind,setKind]=useState('all'),[stage,setStage]=useState('all'),[query,setQuery]=useState(''),[onlyErrors,setOnlyErrors]=useState(false),[newest,setNewest]=useState(false),[page,setPage]=useState(1),[refresh,setRefresh]=useState(0);
 const cursor=useRef(0),attempt=useRef<string|null>(null);
 useEffect(()=>{let active=true;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  void fetch(`/api/admin/jobs/${encodeURIComponent(id)}`,{cache:'no-store',signal:controller.signal}).then(r=>r.ok?r.json() as Promise<{title?:string}>:null).then(v=>{if(active&&v?.title)setTitle(v.title);}).catch(()=>{});
  async function poll(){let delay=3000;try{
   const response=await fetch(`/api/admin/jobs/${encodeURIComponent(id)}/trace?after=${cursor.current}`,{cache:'no-store',signal:controller.signal});
   if([401,403,404].includes(response.status)){if(active){setEvents([]);setError('任务不存在或当前账号没有管理员权限。');}return;}
   if(!response.ok)throw Error();const value=await response.json() as Snapshot;if(!active)return;
   if(attempt.current!==null&&value.attempt!==attempt.current){cursor.current=0;attempt.current=value.attempt;setEvents([]);setPage(1);delay=0;}
   else{attempt.current=value.attempt;cursor.current=value.nextChunk;setSnapshot(value);setError('');
    if(value.events.length)setEvents(previous=>{const map=new Map(previous.map(e=>[e.seq,e]));for(const e of value.events)map.set(e.seq,e);return [...map.values()].sort((a,b)=>a.seq-b.seq);});
    if(value.nextChunk<value.totalChunks)delay=150;
    else if(['complete','failed'].includes(value.status)&&(value.finished||!value.available))return;
   }
  }catch{if(!active)return;setError('暂时无法同步执行记录，正在重试。');delay=6000;}
  if(active)timer=setTimeout(poll,delay);
  }
  void poll();return()=>{active=false;controller.abort();clearTimeout(timer);};
 },[id,refresh]);
 const stages=useMemo(()=>[...new Set(events.map(e=>e.stage))],[events]);
 const visible=useMemo(()=>{const q=query.toLowerCase();const values=events.filter(e=>(kind==='all'||e.kind===kind)&&(stage==='all'||e.stage===stage)&&(!onlyErrors||e.state==='failed'||e.kind==='error')&&[e.label,e.command,e.output,e.detail,e.stage].some(v=>v?.toLowerCase().includes(q)));return newest?values.reverse():values;},[events,kind,stage,query,onlyErrors,newest]);
 const pages=Math.max(1,Math.ceil(visible.length/50)),current=Math.min(page,pages),shown=visible.slice((current-1)*50,current*50);
 const reset=()=>setPage(1);
 function download(){const blob=new Blob(events.map(e=>JSON.stringify(e)+'\n'),{type:'application/x-ndjson;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`execution-${id}.jsonl`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 return <main className="trace-room"><header><a className="brand" href="/admin">PPTX LAB / RICK’S CONTROL ROOM</a><a href={`/jobs/${id}`}>返回任务与页面预览 →</a></header>
 <p className="eyebrow">ADMINISTRATOR / EXECUTION RECORD</p><h1>{title}</h1><p className="trace-intro">查看实际命令、工具输入与输出、工作说明和独立审核结果。按发生顺序保留，支持检索和导出。</p>
 <div className="trace-status"><strong>{snapshot?(['complete','failed'].includes(snapshot.status)?'任务已结束':'实时同步 · 每 3 秒更新'):'正在连接…'}</strong><span>已加载 {events.length} / {snapshot?.totalEvents??0} 条</span><button onClick={()=>setRefresh(n=>n+1)}>立即刷新</button><button disabled={!events.length} onClick={download}>{events.length<(snapshot?.totalEvents??0)?'导出已加载记录':'导出执行记录'}</button></div>
 <p className="fineprint">说明来自助手的可见工作摘要，不展示内部思维链。凭证会隐藏；过长输出会标注截断。命令执行中先显示开始记录，输出返回后补充完成记录。</p>
 {error&&<p className="error" role="alert">{error}</p>}
 <section className="trace-controls" aria-label="筛选执行记录"><label>搜索命令、输出或说明<input type="search" value={query} onChange={e=>{setQuery(e.target.value);reset();}} placeholder="例如：render、字体、报错…"/></label><label>阶段<select value={stage} onChange={e=>{setStage(e.target.value);reset();}}><option value="all">全部阶段</option>{stages.map(s=><option key={s} value={s}>{stageName(s)} · {s}</option>)}</select></label><label>类型<select value={kind} onChange={e=>{setKind(e.target.value);reset();}}><option value="all">全部类型</option>{Object.entries(labels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><button aria-pressed={onlyErrors} onClick={()=>{setOnlyErrors(v=>!v);reset();}}>只看错误</button><button onClick={()=>{setNewest(v=>!v);reset();}}>{newest?'最新在前':'最早在前'} ↕</button></section>
 {!events.length?<div className="trace-empty">{snapshot?.available?'正在加载记录…':snapshot&&['complete','failed'].includes(snapshot.status)?'这个任务没有采集详细执行记录。此功能从新版执行端接手的任务开始生效，历史过程不会补造。':'尚未收到执行记录。任务开始后会显示命令、工具调用和阶段说明。'}</div>:!visible.length?<div className="trace-empty">没有符合条件的记录。</div>:<ol className="trace-events">{shown.map(e=><li key={e.seq}><div className="trace-stamp"><span>#{e.seq}</span><time>{new Date(e.at).toLocaleTimeString('zh-CN')}</time></div><details className={`trace-event ${e.state}`} open={e.kind==='error'}><summary><span className="trace-kind">{labels[e.kind]}</span><strong>{e.command?e.command.split('\n')[0].slice(0,140):e.label}</strong><small>{stageName(e.stage)} · {e.state==='started'?'开始':e.state==='failed'?'失败':'完成'}{e.exitCode!==undefined?` · 退出码 ${e.exitCode}`:''}</small></summary>{e.truncated&&<p className="trace-truncated">这条记录内容较长，在线显示已截断。</p>}{e.command&&<section><h3>实际命令</h3><pre>{e.command}</pre></section>}{e.detail&&<section><h3>{e.kind==='note'?'工作说明':e.kind==='review'?'审核结果':'输入与详情'}</h3><pre>{e.detail}</pre></section>}{e.output!==undefined&&<section><h3>输出</h3><pre>{e.output||'（无输出）'}</pre></section>}{!e.command&&!e.detail&&e.output===undefined&&<p className="fineprint">已记录此操作的状态。</p>}</details></li>)}</ol>}
 <nav className="trace-pagination" aria-label="记录分页"><button disabled={current<=1} onClick={()=>setPage(current-1)}>上一页</button><span>{current} / {pages} · 筛选后 {visible.length} 条</span><button disabled={current>=pages} onClick={()=>setPage(current+1)}>下一页</button></nav>
 </main>;
}
