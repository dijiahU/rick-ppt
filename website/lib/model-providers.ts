// Customer credentials may reach only these fixed, reviewed origins.
// Keep the runner's customer_models.py catalog in sync (covered by tests).
export const modelProviders = {
 openai:{label:'OpenAI',baseUrl:'https://api.openai.com/v1',wireApi:'responses',models:['gpt-6-astra','gpt-6.1-sol','gpt-6-luna'],webSearch:false},
 deepseek:{label:'DeepSeek',baseUrl:'https://api.deepseek.com',wireApi:'responses',models:['deepseek-flash'],webSearch:false},
 siliconflow:{label:'SiliconFlow',baseUrl:'https://api.siliconflow.cn/v1',wireApi:'chat_completions',models:['deepseek-ai/DeepSeek-V4.1-Flash','zai-org/GLM-5.3-Flash','Pro/moonshotai/Kimi-K2.6','Qwen/Qwen3.6-35B-A3B'],webSearch:false},
} as const;
export type ModelProvider=keyof typeof modelProviders;
export const isModelProvider=(v:unknown):v is ModelProvider=>typeof v==='string'&&Object.hasOwn(modelProviders,v);
export const allowedModel=(p:ModelProvider,m:unknown):m is string=>typeof m==='string'&&(modelProviders[p].models as readonly string[]).includes(m);
export type ModelAccount={id:string;provider:ModelProvider;label:string;keyHint:string;models:string[];createdAt:number};
