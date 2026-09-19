import {defineConfig} from 'vite';
import {resolve} from 'node:path';
export default defineConfig(({mode})=>({
 base:'./',
 // A worker's first ONNX import must not trigger a late optimizer page reload.
 optimizeDeps:mode==='test'?{include:['onnxruntime-web/webgpu']}:undefined,
 server:{host:'127.0.0.1',port:41974,strictPort:true,hmr:mode!=='test',fs:{allow:[resolve('..')]}},
 build:{target:'es2022',manifest:true,
  // Production font-src 'self' requires even small KaTeX fonts to be local files.
  assetsInlineLimit:(filePath:string)=>/\.(?:woff2?|ttf|otf)$/i.test(filePath)?false:undefined,
  rollupOptions:{input:{preview:resolve('preview.html'),content:resolve('content.html')}}},
 test:{include:['tests/**/*.test.ts']},
}) as any);
