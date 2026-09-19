import {defineConfig} from 'vite';
import {resolve} from 'node:path';
export default defineConfig({base:'./',server:{host:'127.0.0.1',port:41974,strictPort:true,fs:{allow:[resolve('..')]}},build:{target:'es2022',manifest:true,rollupOptions:{input:{preview:resolve('preview.html'),content:resolve('content.html')}}},test:{include:['tests/**/*.test.ts']}} as any);
