'use client';
import type {Progress} from '@/lib/progress';
import {previewVersion} from '@/lib/creation-progress';
import {reviewWords} from '@/lib/review-i18n';

const words={
 en:{ready:'Your presentation is ready',download:'Download PPTX',pages:'slide previews',content:'Content',visual:'Visuals',editable:'Text, shapes and charts stay editable in PowerPoint or WPS. Click builds play in slideshow mode.',change:'Want a change? Describe it in the conversation and choose “Change request”.',all:'See all slide previews'},
 'zh-CN':{ready:'你的 PPT 已经做好',download:'下载 PPTX',pages:'页预览',content:'内容审核',visual:'视觉审核',editable:'文字、图形和图表都能在 PowerPoint 或 WPS 里直接修改，放映时有点击动画。',change:'想改哪里？在右侧对话里写下来，选择“修改意见”发送即可。',all:'查看全部预览'},
 fr:{ready:'Votre présentation est prête',download:'Télécharger le PPTX',pages:'aperçus de diapositives',content:'Contenu',visual:'Visuel',editable:'Textes, formes et graphiques restent modifiables dans PowerPoint ou WPS.',change:'Une modification ? Décrivez-la dans la conversation.',all:'Voir tous les aperçus'},
 es:{ready:'Tu presentación está lista',download:'Descargar PPTX',pages:'vistas previas',content:'Contenido',visual:'Diseño',editable:'Textos, formas y gráficos siguen siendo editables en PowerPoint o WPS.',change:'¿Quieres un cambio? Descríbelo en la conversación.',all:'Ver todas las vistas previas'},
 ja:{ready:'プレゼンテーションが完成しました',download:'PPTX をダウンロード',pages:'ページのプレビュー',content:'内容レビュー',visual:'デザインレビュー',editable:'文字・図形・グラフは PowerPoint や WPS で編集できます。',change:'修正したい点は会話欄に書いてください。',all:'すべてのプレビューを見る'},
};

export default function DeliveryCard({base,progress,locale,onShowAll,onShowReviews}:{base:string;progress:Progress|null;locale:keyof typeof words;onShowAll:()=>void;onShowReviews:()=>void}){
 const w=words[locale]||words.en;
 const previews=progress?.previews||[];
 const reviews=progress?.reviews;
 const states=(reviewWords[locale]||reviewWords.en).states;
 return <section className="delivery-card" aria-label={w.ready}>
  <div className="delivery-main">
   <h2>{w.ready}</h2>
   <a className="delivery-download" href={`${base}/download`} download>{w.download}</a>
   <ul className="delivery-facts">
    {previews.length>0&&<li><b>{previews.length}</b> {w.pages}</li>}
    {reviews&&<li>{w.content} · {states[reviews.content]}</li>}
    {reviews&&<li>{w.visual} · {states[reviews.visual]}</li>}
    {reviews&&<li><button type="button" className="delivery-link" onClick={onShowReviews}>{(reviewWords[locale]||reviewWords.en).open}</button></li>}
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
