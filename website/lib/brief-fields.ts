import type {Locale} from './i18n';

// Structured brief for new presentations. The answers are composed into the
// existing `brief` text, so the API, queue and worker are unchanged.
export type BriefAnswers={request:string;purpose:string;purposeOther:string;viewing:string;audience:string;familiarity:string;outcome:string;own:string;include:string;avoid:string;notes:string};
export const emptyAnswers:BriefAnswers={request:'',purpose:'',purposeOther:'',viewing:'',audience:'',familiarity:'',outcome:'',own:'',include:'',avoid:'',notes:''};

type Copy={
 legend:string;required:string;optional:string;
 request:string;requestPlaceholder:string;requestHelp:string;titleAuto:string;
 purpose:string;purposes:string[];other:string;otherPlaceholder:string;
 viewing:string;viewingHelp:string;viewings:string[];
 audience:string;audiencePlaceholder:string;familiarity:string;familiarities:string[];
 outcome:string;outcomePlaceholder:string;
 more:string;
 own:string;ownHelp:string;ownPlaceholder:string;
 include:string;includePlaceholder:string;avoid:string;avoidPlaceholder:string;
 notes:string;notesPlaceholder:string;
 preview:string;missing:string;remove:string;
 lines:{request:string;purpose:string;viewing:string;audience:string;familiarity:string;outcome:string;own:string;ownNone:string;include:string;avoid:string;notes:string};
};

export const briefCopy:Record<Locale,Copy>={
 'zh-CN':{request:"你想做一份什么样的 PPT？",requestPlaceholder:"写下主题和要讲的内容。手上有的数字、价格、人名、产品名也写在这里，例如：给初二学生讲浮力，3 个班、每班 42 人，要有溢水杯实验的步骤。",requestHelp:"写得越具体越贴近你要的。没给的数字会先用标了“示例”的数值占位。",titleAuto:"取自上面第一句，可以直接修改。",legend:'先回答几个问题，做出来会更贴近你要的',required:'必填',optional:'选填',
  purpose:'这份 PPT 用在什么场合？',purposes:['课堂讲课','工作汇报','项目路演 / 融资','产品发布','学术报告','培训分享','品牌介绍'],other:'其他',otherPlaceholder:'写下场合，例如：婚礼致辞',
  viewing:'观众怎么看？',viewingHelp:'决定每页放多少字：现场讲字少图大，发文件看要能独立读懂。',viewings:['我在现场投影讲','线上会议共享屏幕','发给别人自己看','打印出来'],
  audience:'谁来看？',audiencePlaceholder:'例如：初二学生、公司管理层、咖啡店店主',familiarity:'他们对这个主题',familiarities:['第一次接触','有一定了解','是行内专家'],
  outcome:'看完之后，希望他们记住什么或做什么？',outcomePlaceholder:'例如：理解浮力和排开水的体积有关；同意试饮合作',
  more:'让内容更准（选填）',
  own:'只有你知道的信息',ownHelp:'数字、价格、团队、案例、产品名等。没有就留空，会先用标明“示例”的数字占位。',ownPlaceholder:'例如：门店 3 家，月销 1200 杯，主打豆子叫“焦糖”',
  include:'一定要讲到的内容',includePlaceholder:'例如：实验步骤、价格表、联系方式',avoid:'不要出现的内容或样子',avoidPlaceholder:'例如：不要卡通风、不要提竞品名字',
  notes:'其他补充',notesPlaceholder:'任何想说明的：参考风格、讲者身份、时长、特殊要求……',
  preview:'将要提交的需求',missing:'还差：',remove:'撕掉',
  lines:{request:"需求",purpose:'场合',viewing:'观看方式',audience:'观众',familiarity:'观众对主题',outcome:'希望观众记住或做到',own:'我提供的信息',ownNone:"需求里没有给出的数字，请用合理的示例值并在页上标注“示例数字，非真实数据”",include:'必须包含',avoid:'不要出现',notes:'其他补充'}},
 en:{request:"What presentation do you need?",requestPlaceholder:"Describe the topic and what it should cover. Put the figures, prices, names and product names you already have here too, e.g. buoyancy for grade 8, three classes of 42, include the overflow-can experiment steps.",requestHelp:"The more specific, the closer the result. Figures you leave out are filled with values labelled as examples.",titleAuto:"Taken from your first sentence. Edit it if you like.",legend:'A few questions first, so the deck fits what you need',required:'Required',optional:'Optional',
  purpose:'What is this presentation for?',purposes:['Teaching a class','Work report','Pitch / fundraising','Product launch','Academic talk','Training','Brand introduction'],other:'Other',otherPlaceholder:'Describe the occasion, e.g. a wedding speech',
  viewing:'How will people see it?',viewingHelp:'This sets how much goes on each slide: presented live means fewer words, sent as a file means it must read on its own.',viewings:['I present it in the room','Shared on a video call','Sent for people to read','Printed'],
  audience:'Who is the audience?',audiencePlaceholder:'e.g. grade 8 students, the leadership team, café owners',familiarity:'How well do they know the topic?',familiarities:['New to it','Somewhat familiar','Experts'],
  outcome:'What should they remember or do afterwards?',outcomePlaceholder:'e.g. understand that buoyancy depends on displaced water; agree to a trial order',
  more:'Make the content more precise (optional)',
  own:'Information only you have',ownHelp:'Figures, prices, team, cases, product names. Leave empty and labelled example figures are used instead.',ownPlaceholder:'e.g. 3 shops, 1,200 cups a month, our main blend is called “Caramel”',
  include:'Must be covered',includePlaceholder:'e.g. experiment steps, price list, contact details',avoid:'Leave out',avoidPlaceholder:'e.g. no cartoon style, no competitor names',
  notes:'Anything else',notesPlaceholder:'Reference style, who is speaking, duration, special requests…',
  preview:'Brief that will be submitted',missing:'Still needed: ',remove:'Remove',
  lines:{request:"Request",purpose:'Occasion',viewing:'Viewing',audience:'Audience',familiarity:'Audience familiarity',outcome:'Audience should remember or do',own:'Information I provide',ownNone:"Where the request gives no figure, use a plausible example value labelled “Illustrative figure” on the slide",include:'Must include',avoid:'Leave out',notes:'Other notes'}},
 fr:{request:"Quelle présentation vous faut-il ?",requestPlaceholder:"Décrivez le sujet et ce qu’elle doit couvrir. Ajoutez ici les chiffres, prix, noms et produits dont vous disposez.",requestHelp:"Plus c’est précis, plus le résultat sera proche. Les chiffres manquants sont remplacés par des valeurs signalées comme exemples.",titleAuto:"Repris de votre première phrase. Modifiable.",legend:'Quelques questions pour une présentation qui vous correspond',required:'Obligatoire',optional:'Facultatif',
  purpose:'À quoi sert cette présentation ?',purposes:['Cours','Rapport','Pitch / levée de fonds','Lancement de produit','Conférence','Formation','Présentation de marque'],other:'Autre',otherPlaceholder:'Décrivez l’occasion',
  viewing:'Comment sera-t-elle vue ?',viewingHelp:'Présentée en direct : peu de texte. Envoyée : doit se lire seule.',viewings:['Je la présente sur place','Partagée en visio','Envoyée à lire','Imprimée'],
  audience:'Qui est le public ?',audiencePlaceholder:'ex. élèves de 4e, direction, cafetiers',familiarity:'Leur connaissance du sujet',familiarities:['Débutants','Un peu','Experts'],
  outcome:'Que doivent-ils retenir ou faire ensuite ?',outcomePlaceholder:'ex. comprendre la poussée d’Archimède ; accepter un essai',
  more:'Préciser le contenu (facultatif)',
  own:'Informations que vous seul avez',ownHelp:'Chiffres, prix, équipe, cas, noms de produits. Sinon, des chiffres d’exemple signalés sont utilisés.',ownPlaceholder:'ex. 3 boutiques, 1 200 tasses par mois',
  include:'À couvrir absolument',includePlaceholder:'ex. étapes, tarifs, contact',avoid:'À éviter',avoidPlaceholder:'ex. pas de style cartoon',
  notes:'Autres précisions',notesPlaceholder:'Style de référence, orateur, durée…',
  preview:'Brief qui sera envoyé',missing:'À compléter : ',remove:'Retirer',
  lines:{request:"Demande",purpose:'Occasion',viewing:'Visionnage',audience:'Public',familiarity:'Connaissance du sujet',outcome:'Le public doit retenir ou faire',own:'Informations fournies',ownNone:"Quand la demande ne donne pas de chiffre, utiliser une valeur d’exemple plausible, signalée sur la diapositive",include:'À inclure',avoid:'À éviter',notes:'Autres précisions'}},
 es:{request:"¿Qué presentación necesitas?",requestPlaceholder:"Describe el tema y lo que debe cubrir. Añade aquí las cifras, precios, nombres y productos que ya tengas.",requestHelp:"Cuanto más concreto, más cerca del resultado. Las cifras que falten se rellenan con valores señalados como ejemplo.",titleAuto:"Tomado de tu primera frase. Puedes cambiarlo.",legend:'Unas preguntas primero para que la presentación encaje',required:'Obligatorio',optional:'Opcional',
  purpose:'¿Para qué es esta presentación?',purposes:['Clase','Informe de trabajo','Pitch / inversión','Lanzamiento de producto','Ponencia académica','Formación','Presentación de marca'],other:'Otro',otherPlaceholder:'Describe la ocasión',
  viewing:'¿Cómo la verán?',viewingHelp:'En directo: pocas palabras. Enviada: debe entenderse sola.',viewings:['La presento en la sala','Compartida en videollamada','Enviada para leer','Impresa'],
  audience:'¿Quién es el público?',audiencePlaceholder:'p. ej. alumnos de 2.º de ESO, la dirección, dueños de cafeterías',familiarity:'¿Cuánto conocen el tema?',familiarities:['Nada','Algo','Son expertos'],
  outcome:'¿Qué deben recordar o hacer después?',outcomePlaceholder:'p. ej. entender el empuje; aceptar una prueba',
  more:'Precisar el contenido (opcional)',
  own:'Información que solo tú tienes',ownHelp:'Cifras, precios, equipo, casos, nombres de producto. Si no, se usan cifras de ejemplo señaladas.',ownPlaceholder:'p. ej. 3 tiendas, 1.200 tazas al mes',
  include:'Debe incluir',includePlaceholder:'p. ej. pasos, precios, contacto',avoid:'Evitar',avoidPlaceholder:'p. ej. sin estilo de dibujos',
  notes:'Otras notas',notesPlaceholder:'Estilo de referencia, ponente, duración…',
  preview:'Encargo que se enviará',missing:'Falta: ',remove:'Quitar',
  lines:{request:"Encargo",purpose:'Ocasión',viewing:'Visualización',audience:'Público',familiarity:'Conocimiento del tema',outcome:'El público debe recordar o hacer',own:'Información aportada',ownNone:"Si el encargo no da una cifra, usar un valor de ejemplo plausible, señalado en la diapositiva",include:'Debe incluir',avoid:'Evitar',notes:'Otras notas'}},
 ja:{request:"どんな資料を作りますか？",requestPlaceholder:"テーマと入れたい内容を書いてください。手元の数字、価格、人名、製品名もここに。",requestHelp:"具体的なほど意図に近づきます。書かれていない数字は「例」と明記した値で補います。",titleAuto:"最初の一文から自動で入ります。変更できます。",legend:'まずいくつか教えてください。目的に合った資料になります',required:'必須',optional:'任意',
  purpose:'どんな場面で使いますか？',purposes:['授業','業務報告','ピッチ / 資金調達','製品発表','学会発表','研修','ブランド紹介'],other:'その他',otherPlaceholder:'場面を入力',
  viewing:'どのように見られますか？',viewingHelp:'会場で話すなら文字は少なく、配布するなら単独で読める内容にします。',viewings:['会場で投影して話す','オンライン会議で画面共有','ファイルを送って読んでもらう','印刷する'],
  audience:'誰が見ますか？',audiencePlaceholder:'例：中学2年生、経営陣、カフェのオーナー',familiarity:'テーマへの理解度',familiarities:['初めて','ある程度知っている','専門家'],
  outcome:'見終わった後、何を覚えて／してほしいですか？',outcomePlaceholder:'例：浮力が押しのけた水の体積で決まると理解する',
  more:'内容をより正確に（任意）',
  own:'あなたしか知らない情報',ownHelp:'数字、価格、チーム、事例、製品名など。空欄なら「例」と明記した数字を使います。',ownPlaceholder:'例：3店舗、月1,200杯',
  include:'必ず入れる内容',includePlaceholder:'例：手順、価格表、連絡先',avoid:'入れたくない内容や雰囲気',avoidPlaceholder:'例：アニメ調にしない',
  notes:'その他',notesPlaceholder:'参考スタイル、話者、時間、特別な要望…',
  preview:'送信される依頼内容',missing:'未入力：',remove:'はがす',
  lines:{request:"依頼内容",purpose:'場面',viewing:'見られ方',audience:'聞き手',familiarity:'テーマへの理解度',outcome:'覚えて／してほしいこと',own:'提供する情報',ownNone:"依頼に数字がない場合は妥当な例の数値を使い、スライドに「例の数値」と明記",include:'必ず入れる',avoid:'入れない',notes:'その他'}},
};

export function purposeText(a:BriefAnswers){return a.purpose==='other'?a.purposeOther.trim():a.purpose;}

/** What must be answered before the brief can be sent: the request itself, the occasion and how it will be viewed. */
export function missingFields(a:BriefAnswers,c:Copy){
 const out:string[]=[];
 if(a.request.trim().length<6)out.push(c.lines.request);
 if(!purposeText(a))out.push(c.lines.purpose);
 if(!a.viewing)out.push(c.lines.viewing);
 return out;
}

export function composeBrief(a:BriefAnswers,locale:Locale){
 const c=briefCopy[locale]||briefCopy.en,l=c.lines,sep=locale==='zh-CN'||locale==='ja'?'：':': ';
 const rows:[string,string][]= [
  [l.request,a.request.trim()],
  [l.purpose,purposeText(a)],[l.viewing,a.viewing],
  [l.audience,a.audience.trim()],[l.familiarity,a.familiarity],
  [l.outcome,a.outcome.trim()],[l.own,a.own.trim()||l.ownNone],
  [l.include,a.include.trim()],[l.avoid,a.avoid.trim()],[l.notes,a.notes.trim()],
 ];
 return rows.filter(([,v])=>v).map(([k,v])=>k+sep+v).join('\n');
}

/**
 * A short title from what the visitor wrote: the first sentence of the first line, cut to about 40 Chinese
 * characters or 80 Latin ones, at a word boundary where there is one. Rule-based; no model is involved.
 */
export function deriveTitle(text:string,budget=80){
 const line=text.trim().split('\n')[0]??'';
 const sentence=(line.split(/(?<=[。！？!?；;])|(?<=\.)\s/u)[0]??'').replace(/[。！？!?；;.，,：:\s]+$/u,'').trim();
 let used=0,out='';
 for(const ch of Array.from(sentence)){used+=/[^\x00-\xff]/.test(ch)?2:1;if(used>budget)break;out+=ch;}
 if(out===sentence)return out;
 const space=out.lastIndexOf(' ');
 return (space>out.length-16&&space>0?out.slice(0,space):out).replace(/[，,：:\s]+$/u,'')+'…';
}
