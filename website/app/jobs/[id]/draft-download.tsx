import type {Draft} from '@/lib/drafts';
const words={
 'zh-CN':['下载最近进度 PPT','进度版 · 未最终验收','页','保存于','这是最近一次成功导出的版本，可能早于当前页面预览。交互功能仍需配套运行环境。','还没有成功导出的进度文件。首次导出后会在这里提供下载。'],
 en:['Download latest progress PPT','Progress copy · not finally reviewed','pages','Saved','This is the last successful export and may precede the current previews. Interactive features still require their runtime.','No successful progress export yet. A download will appear here after the first export.'],
 fr:['Télécharger le PPT en cours','Version provisoire · non validée','pages','Enregistré','Dernier export réussi, parfois antérieur aux aperçus. Les interactions nécessitent leur environnement.','Aucun export réussi pour le moment.'],
 es:['Descargar PPT en curso','Versión provisional · sin revisión final','páginas','Guardado','Última exportación correcta; puede ser anterior a las vistas previas. Las interacciones requieren su entorno.','Aún no hay una exportación correcta.'],
 ja:['進捗版 PPT をダウンロード','進捗版 · 最終確認前','ページ','保存日時','最後に正常に出力された版です。プレビューより古い場合があります。操作には実行環境が必要です。','正常に出力された進捗版はまだありません。']
};
export default function DraftDownload({draft,base,locale}:{draft:Draft|null;base:string;locale:keyof typeof words}){
 const w=words[locale];return <section className="room-brief" aria-label={w[1]}><strong>{w[1]}</strong>{draft?<><p><a className="download" href={`${base}/draft`}>{w[0]} ↓</a></p><p>{draft.pages} {w[2]} · {w[3]} {new Date(draft.saved_at).toLocaleString(locale)}</p><p className="fineprint">{w[4]}</p></>:<p className="fineprint">{w[5]}</p>}</section>;
}
