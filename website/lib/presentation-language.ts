import {isLocale,type Locale} from './i18n';

// An explicit picker wins. Automatic defaults remain visible and overridable;
// only the resolved literal is admitted as the immutable task language.
export function resolvePresentationLanguage(brief:string,ui:Locale,override:Locale|null,mode:'create'|'edit'='create'){
 if(isLocale(override))return {language:override,source:'selected' as const};
 const requests:[Locale,RegExp][]=[
  ['zh-CN',/(?:用|使用|输出为|语言[：:]?\s*)(?:简体)?中文|(?:简体)?中文(?:版|\s*(?:ppt|演示|幻灯片))|(?:presentation|slides?|ppt|output).*?in\s+(?:simplified\s+)?chinese/iu],
  ['en',/(?:用|使用|输出为|语言[：:]?\s*)英文|英文(?:版|\s*(?:ppt|演示|幻灯片))|(?:presentation|slides?|ppt|output).*?in\s+english/iu],
  ['ja',/(?:用|使用|输出为|语言[：:]?\s*)(?:日文|日语)|(?:日文|日语)版|(?:presentation|slides?|ppt|output).*?in\s+japanese/iu],
  ['fr',/(?:用|使用|输出为|语言[：:]?\s*)法语|法语版|(?:presentation|slides?|ppt|output).*?in\s+french/iu],
  ['es',/(?:用|使用|输出为|语言[：:]?\s*)西班牙语|西班牙语版|(?:presentation|slides?|ppt|output).*?in\s+spanish/iu]
 ];
 const matches=requests.filter(([,pattern])=>pattern.test(brief));
 if(matches.length===1)return {language:matches[0][0],source:'brief' as const};
 // No language model call; a strong script majority is only an editable default.
 const letters=[...brief].filter(c=>/\p{Letter}/u.test(c));
 const cjk=letters.filter(c=>/[\u3400-\u9fff\u3040-\u30ff]/u.test(c)).length;
 if(mode==='create'&&matches.length===0&&letters.length>=10&&cjk/letters.length>.5){
  return {language:(/[\u3040-\u30ff]/u.test(brief)?'ja':'zh-CN') as Locale,source:'brief' as const};
 }
 return {language:ui,source:'default' as const};
}
export const languageResolutionMessages={
 en:{selected:'Selected output language',brief:'Suggested from your brief',default:'Default output language'},
 'zh-CN':{selected:'手动选择的成品语言',brief:'根据需求建议的成品语言',default:'默认成品语言'},
 fr:{selected:'Langue de sortie choisie',brief:'Langue suggérée par le brief',default:'Langue de sortie par défaut'},
 es:{selected:'Idioma de salida elegido',brief:'Idioma sugerido por el encargo',default:'Idioma de salida predeterminado'},
 ja:{selected:'選択した出力言語',brief:'依頼文から提案した言語',default:'既定の出力言語'}
};
