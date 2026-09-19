import type {Locale} from './i18n';
type Words = {
  allTasks:string; adminHelp:string; queue:string; lastSeen:string; neverSeen:string;
  running:string; position:string; waited:string; oldest:string; minutes:string;
  offline:string; busy:string; waiting:string; idle:string;
};
export const queueWords:Record<Locale,Words> = {
  'zh-CN': {
    allTasks:'所有用户的任务', adminHelp:'查看每位用户的提交内容、实时进度、页面预览和结果。',
    queue:'队列与执行状态', lastSeen:'执行器最近在线', neverSeen:'尚未连接',
    running:'正在执行', position:'排队位置', waited:'已等待', oldest:'最长等待', minutes:'分钟',
    offline:'执行器离线，排队任务暂时无法开始。恢复连接后会按提交顺序处理，无需重复提交。',
    busy:'执行名额已满，正在等待当前任务释放名额。',
    waiting:'执行器在线，正在等待接收任务。', idle:'执行器在线，目前没有排队任务。',
  },
  en: {
    allTasks:'All users’ tasks', adminHelp:'View everyone’s requests, live progress, slide previews and results.',
    queue:'Queue and execution', lastSeen:'Worker last seen', neverSeen:'Never connected',
    running:'Running', position:'Queue position', waited:'Waiting for', oldest:'Longest wait', minutes:'min',
    offline:'The worker is offline, so queued tasks cannot start. They will be processed in submission order when it reconnects. No need to resubmit.',
    busy:'All execution slots are occupied. Waiting for a running task to finish.',
    waiting:'The worker is online. Waiting for task pickup.', idle:'The worker is online. No tasks are queued.',
  },
  fr: {
    allTasks:'Demandes de tous les utilisateurs', adminHelp:'Consultez les demandes, la progression, les aperçus et les résultats de chacun.',
    queue:'File et exécution', lastSeen:'Dernière connexion', neverSeen:'Jamais connecté',
    running:'En cours', position:'Position', waited:'Attente', oldest:'Attente maximale', minutes:'min',
    offline:'L’exécuteur est déconnecté. Les demandes reprendront dans l’ordre à sa reconnexion. Inutile de les renvoyer.',
    busy:'Toutes les places sont occupées. En attente de la fin d’une demande.',
    waiting:'L’exécuteur est connecté. En attente de prise en charge.', idle:'L’exécuteur est connecté. Aucune demande en attente.',
  },
  es: {
    allTasks:'Tareas de todos los usuarios', adminHelp:'Consulta solicitudes, progreso, vistas previas y resultados de todos.',
    queue:'Cola y ejecución', lastSeen:'Última conexión', neverSeen:'Nunca conectado',
    running:'En ejecución', position:'Posición en cola', waited:'En espera', oldest:'Espera más larga', minutes:'min',
    offline:'El ejecutor está desconectado. Las tareas se procesarán por orden al reconectarse. No es necesario reenviarlas.',
    busy:'Todas las plazas están ocupadas. Esperando a que termine una tarea.',
    waiting:'El ejecutor está conectado. Esperando la recogida de tareas.', idle:'El ejecutor está conectado. No hay tareas en cola.',
  },
  ja: {
    allTasks:'全ユーザーのタスク', adminHelp:'全員の依頼内容、進捗、プレビュー、結果を確認できます。',
    queue:'待機と実行状況', lastSeen:'最終接続', neverSeen:'未接続',
    running:'実行中', position:'待機順', waited:'待機時間', oldest:'最長待機', minutes:'分',
    offline:'実行端末がオフラインです。再接続後、送信順に処理されます。再送信は不要です。',
    busy:'実行枠がすべて使用中です。実行中のタスクの完了を待っています。',
    waiting:'実行端末はオンラインです。タスクの受付を待っています。', idle:'実行端末はオンラインです。待機中のタスクはありません。',
  },
};
