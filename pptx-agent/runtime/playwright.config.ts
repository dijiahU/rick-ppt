import {defineConfig,devices} from '@playwright/test';
const runId=process.env.PPTX_BROWSER_RUN_ID??=new Date().toISOString().replace(/[:.]/g,'-')+'-'+process.pid;
export default defineConfig({
 testDir:'./tests',testMatch:'**/*.spec.ts',timeout:45000,expect:{timeout:10000},fullyParallel:true,workers:2,
 outputDir:'test-results/browser/'+runId,reporter:[['list'],['html',{outputFolder:'playwright-report/'+runId,open:'never'}]],
 use:{baseURL:'http://127.0.0.1:41976',viewport:{width:1280,height:800},trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome'],viewport:{width:1280,height:800}}}],
 webServer:{command:'npm run dev -- --port 41976',url:'http://127.0.0.1:41976/preview.html',reuseExistingServer:!process.env.CI,timeout:60000},
});
