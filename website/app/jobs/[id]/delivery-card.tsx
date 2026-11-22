'use client';
import type {Progress} from '@/lib/progress';
import {previewVersion} from '@/lib/creation-progress';

const words={
 en:{ready:'Your presentation is ready',download:'Download PPTX',pages:'slides',content:'Content',visual:'Visuals',passed:'reviewed',open:'reviewed with notes',editable:'Text, shapes and charts stay editable in PowerPoint or WPS. Click builds play in slideshow mode.',change:'Want a change? Describe it in the conversation and choose “Change request”.',all:'See every slide'},
 'zh-CN':{ready:'你的 PPT 已经做好',download:'下载 PPTX',pages:'页',content:'内容审核',visual:'视觉审核',passed:'已通过',open:'已审核，附建议',editable:'文字、图形和图表都能在 PowerPoint 或 WPS 里直接修改，放映时有点击动画。',change:'想改哪里？在右侧对话里写下来，选择“修改意见”发送即可。',all:'查看全部页面'},
 fr:{ready:'Votre présentation est prête',download:'Télécharger le PPTX',pages:'diapositives',content:'Contenu',visual:'Visuel',passed:'validé',open:'validé avec remarques',editable:'Textes, formes et graphiques restent modifiables dans PowerPoint ou WPS.',change:'Une modification ? Décrivez-la dans la conversation.',all:'Voir toutes les diapositives'},
 es:{ready:'Tu presentación está lista',download:'Descargar PPTX',pages:'diapositivas',content:'Contenido',visual:'Diseño',passed:'revisado',open:'revisado con notas',editable:'Textos, formas y gráficos siguen siendo editables en PowerPoint o WPS.',change:'¿Quieres un cambio? Descríbelo en la conversación.',all:'Ver todas las diapositivas'},
 ja:{ready:'プレゼンテーションが完成しました',download:'PPTX をダウンロード',pages:'ページ',content:'内容レビュー',visual:'デザインレビュー',passed:'合格',open:'指摘付きで確認済み',editable:'文字・図形・グラフは PowerPoint や WPS で編集できます。',change:'修正したい点は会話欄に書いてください。',all:'すべてのページを見る'},
};

export default function DeliveryCard({base,progress,locale,onShowAll}:{base:string;progress:Progress|null;locale:keyof typeof words;onShowAll:()=>void}){
 const w=words[locale]||words.en;
 const previews=progress?.previews||[];
 const reviews=progress?.reviews;
 const state=(s?:string)=>s==='passed'?w.passed:w.open;
 return <section className="delivery-card" aria-label={w.ready}>
  <div className="delivery-main">
   <h2>{w.ready}</h2>
   <a className="delivery-download" href={`${base}/download`} download>{w.download}</a>
   <ul className="delivery-facts">
    {previews.length>0&&<li><b>{previews.length}</b> {w.pages}</li>}
    {reviews&&<li>{w.content} · {state(reviews.content)}</li>}
    {reviews&&<li>{w.visual} · {state(reviews.visual)}</li>}
   </ul>
   <p>{w.editable}</p>
   <p className="delivery-change">{w.change}</p>
  </div>
  {progress&&previews.length>0&&<button type="button" className="delivery-strip" onClick={onShowAll} aria-label={w.all}>
   {previews.slice(0,4).map(n=><img key={n} src={`${base}/preview/${n}?v=${previewVersion(progress,n)}`} alt="" loading="lazy"/>)}
   <span>{w.all}</span>
  </button>}
 </section>;
}
