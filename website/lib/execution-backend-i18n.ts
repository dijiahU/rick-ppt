import {isExecutionBackend, type ExecutionBackend} from './execution-backend';
import type {Locale} from './i18n';

export const executionWords = {
  en: {label:'Creation method',choose:'Choose a method',api:'API',codex:'Local Codex',localDefault:'Local Codex · Astra · high',help:'Choose how this task will be created. The choice stays with the task.',offline:'The worker is offline. Your chosen method will wait in the queue.',unavailable:'This method is not currently available.',missing:'Choose API or Local Codex before submitting.',locked:'This submission already uses another method. Check your task history before retrying.',legacy:'Historical task · method not recorded'},
  'zh-CN': {label:'制作方式',choose:'请选择制作方式',api:'API',codex:'本地 Codex',localDefault:'本地 Codex · Astra · high',help:'为本次任务选择制作方式，提交后保持不变。',offline:'执行端暂未在线，所选方式将排队等待。',unavailable:'这种制作方式暂不可用。',missing:'请先选择 API 或本地 Codex。',locked:'这次提交已选择另一种方式，请先查看任务记录再重试。',legacy:'历史任务 · 制作方式未记录'},
  fr: {label:'Mode de création',choose:'Choisir un mode',api:'API',codex:'Codex local',localDefault:'Codex local · Astra · high',help:'Choisissez le mode de cette demande. Il sera conservé.',offline:'Le service est hors ligne. Le mode choisi restera en attente.',unavailable:'Ce mode est actuellement indisponible.',missing:'Choisissez API ou Codex local avant l’envoi.',locked:'Cet envoi utilise déjà un autre mode. Vérifiez votre historique avant de réessayer.',legacy:'Ancienne demande · mode non enregistré'},
  es: {label:'Método de creación',choose:'Elige un método',api:'API',codex:'Codex local',localDefault:'Codex local · Astra · high',help:'Elige el método de esta solicitud. Se conservará después del envío.',offline:'El servicio está desconectado. El método elegido quedará en cola.',unavailable:'Este método no está disponible actualmente.',missing:'Elige API o Codex local antes de enviar.',locked:'Este envío ya usa otro método. Consulta el historial antes de reintentar.',legacy:'Solicitud histórica · método no registrado'},
  ja: {label:'作成方法',choose:'作成方法を選択',api:'API',codex:'ローカル Codex',localDefault:'ローカル Codex · Astra · high',help:'このタスクの作成方法を選びます。送信後は変更できません。',offline:'実行端末はオフラインです。選んだ方法で待機します。',unavailable:'この作成方法は現在利用できません。',missing:'送信前に API またはローカル Codex を選んでください。',locked:'この送信は別の方法で受け付け済みです。再試行前に履歴を確認してください。',legacy:'過去のタスク · 作成方法の記録なし'},
};

export function executionLabel(value: ExecutionBackend | null | undefined, locale: Locale): string {
  return isExecutionBackend(value) ? executionWords[locale][value] : executionWords[locale].legacy;
}
