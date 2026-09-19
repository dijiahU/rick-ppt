import {defineConfig,devices} from '@playwright/test';
import {resolve} from 'node:path';
import {existsSync} from 'node:fs';
const root=resolve(import.meta.dirname,'../..');
const python=process.env.PPTX_TEST_PYTHON??(existsSync(resolve(root,'../.venv/bin/python'))?resolve(root,'../.venv/bin/python'):'python3');
const quote=(value:string)=>"'"+value.replaceAll("'","'\\''")+"'";
const runId=new Date().toISOString().replace(/[:.]/g,'-')+'-'+process.pid;
export default defineConfig({testDir:'.',testMatch:'diagnostics-performance.spec.ts',timeout:45000,expect:{timeout:10000},workers:1,reporter:'list',outputDir:`../../test-results/diagnostics-production/${runId}`,projects:[{name:'production-chromium',use:{...devices['Desktop Chrome'],baseURL:'http://127.0.0.1:41978',viewport:{width:1000,height:700},trace:'retain-on-failure',screenshot:'only-on-failure'}}],webServer:{command:`${quote(python)} -m pptx_core.interactive_server --root . --runtime dist --http --port 41978`,cwd:root,url:'http://127.0.0.1:41978/api/health',reuseExistingServer:false,timeout:15000}});
