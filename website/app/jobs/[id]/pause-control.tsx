'use client';
import {useState} from 'react';
const words={en:['Pause task','Stopping…','Stop requested. Saving progress.','Paused. No further work will start until you resume.','Could not pause. Refresh and retry.'],
 'zh-CN':['暂停任务','正在停止…','已请求停止，正在保存进度。','已暂停。只有点击继续后才会重新制作。','暂停失败，请刷新后重试。'],
 fr:['Mettre en pause','Arrêt…','Arrêt demandé. Sauvegarde en cours.','En pause jusqu’à votre reprise.','Actualisez et réessayez.'],
 es:['Pausar tarea','Deteniendo…','Guardando el progreso.','Pausada hasta que la reanudes.','Actualiza y reintenta.'],
 ja:['タスクを一時停止','停止中…','進捗を保存しています。','再開するまで作業は停止します。','更新して再試行してください。']};
export default function PauseControl({id,status,updatedAt,pending,locale,onChange}:{id:string;status:string;updatedAt:number;pending:boolean;locale:keyof typeof words;onChange:()=>void}){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),w=words[locale];
 async function pause(){setBusy(true);setError('');try{const r=await fetch(`/api/jobs/${id}/pause`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expectedUpdatedAt:updatedAt})});if(!r.ok)throw Error(w[4]);onChange();}catch{setError(w[4]);}finally{setBusy(false);}}
 return <>{['queued','running'].includes(status)&&<button disabled={busy} onClick={()=>void pause()}>{busy?w[1]:w[0]}</button>}{status==='paused'&&<span role="status">{pending?w[2]:w[3]}</span>}{error&&<span role="alert">{error}</span>}</>;
}
