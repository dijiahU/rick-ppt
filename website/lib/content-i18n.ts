import type {ReviewState} from './progress';
type Words={outline:string;style:string;content:string;visual:string;review:string;states:Record<ReviewState,string>};
const en:Words={outline:'Presentation outline',style:'Visual direction',content:'Content',visual:'Visuals',review:'Independent reviews',states:{pending:'Pending',reviewing:'Reviewing',changes_requested:'Revising',passed:'Reviewed',unverified:'Static review complete · playback unverified'}};
const words:Record<string,Words>={
 en,
 'zh-CN':{outline:'内容大纲',style:'整体风格',content:'内容',visual:'视觉',review:'独立审核',states:{pending:'等待审核',reviewing:'正在审核',changes_requested:'修改中',passed:'已审核',unverified:'静态已审核 · 播放待验证'}},
 fr:{outline:'Plan de la présentation',style:'Direction visuelle',content:'Contenu',visual:'Visuel',review:'Relectures indépendantes',states:{pending:'En attente',reviewing:'En cours',changes_requested:'Révision',passed:'Relu',unverified:'Non vérifié'}},
 es:{outline:'Esquema de la presentación',style:'Dirección visual',content:'Contenido',visual:'Diseño',review:'Revisiones independientes',states:{pending:'Pendiente',reviewing:'En revisión',changes_requested:'Corrigiendo',passed:'Revisado',unverified:'Sin verificar'}},
 ja:{outline:'プレゼンテーションの構成',style:'全体のデザイン',content:'内容',visual:'ビジュアル',review:'独立したレビュー',states:{pending:'レビュー待ち',reviewing:'レビュー中',changes_requested:'修正中',passed:'レビュー済み',unverified:'未検証'}},
};
export const contentWords=(locale:string)=>words[locale]??en;
