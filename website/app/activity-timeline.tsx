'use client';
import type {Progress} from '@/lib/progress';
import {useLanguage} from './language';
const words={
 en:['Public progress note','Recorded activity','Source','Latest 500 events · Public summaries and tool activity, not a screen broadcast or private reasoning.','Started','Completed','Failed'],
 'zh-CN':['公开进度说明','工具活动记录','来源','最近 500 条记录 · 公开说明与工具活动，不是屏幕直播或内部思维链。','已开始','已完成','未完成'],
 fr:['Note de progression','Activité enregistrée','Source','500 derniers événements · Résumés publics et outils, sans diffusion d’écran ni raisonnement privé.','Démarré','Terminé','Échec'],
 es:['Nota de progreso','Actividad registrada','Fuente','Últimos 500 eventos · Resúmenes públicos y herramientas, no pantalla ni razonamiento privado.','Iniciado','Completado','Fallido'],
 ja:['公開の進捗説明','活動記録','出典','最新500件 · 公開説明とツール活動のみ。画面配信や内部推論ではありません。','開始','完了','失敗']
};
export default function ActivityTimeline({events}:{events:Progress['events']}){
 const {locale,t}=useLanguage(),w=words[locale];
 return <><p className="fineprint">{w[3]}</p><ol className="activity-log">{events.map(e=><li key={e.seq}>
 <time>{new Date(e.at).toLocaleTimeString(locale)}</time><div>
 {e.detail||e.url?<details className="activity-detail"><summary>{t.activities[e.code]}{e.state?` · ${w[4+['started','completed','failed'].indexOf(e.state)]}`:''}</summary>
 <small>{e.reported?w[0]:w[1]}</small>{e.detail&&<p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{e.detail}</p>}
 {e.url&&<a href={e.url} target="_blank" rel="noreferrer noopener">{w[2]}: {new URL(e.url).hostname} ↗</a>}</details>:<span>{t.activities[e.code]}</span>}
 </div></li>)}</ol></>;
}
