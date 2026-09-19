import fs from 'node:fs/promises';
import path from 'node:path';
import {deflateSync} from 'node:zlib';
const root=path.resolve(import.meta.dirname,'..');
const config=JSON.parse(await fs.readFile(path.join(root,'config.json'),'utf8'));
if(!/^[a-f0-9-]{36}$/.test(config.addinId)||!/^https:\/\/localhost:\d+$/.test(config.origin))throw Error('Invalid runtime identity/origin');
const out=path.join(root,'manifests');await fs.mkdir(out,{recursive:true});
const xml=`<?xml version="1.0" encoding="UTF-8"?>
<OfficeApp xmlns="http://schemas.microsoft.com/office/appforoffice/1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ContentApp">
  <Id>${config.addinId}</Id><Version>${config.version}</Version><ProviderName>Rick PPT</ProviderName>
  <DefaultLocale>en-US</DefaultLocale><DisplayName DefaultValue="Rick Interactive Runtime"/>
  <Description DefaultValue="Interactive learning scenes embedded in PowerPoint slides."/>
  <IconUrl DefaultValue="${config.origin}/icons/icon-32.png"/>
  <HighResolutionIconUrl DefaultValue="${config.origin}/icons/icon-64.png"/>
  <SupportUrl DefaultValue="https://github.com/dijiahU/rick-ppt"/>
  <AppDomains><AppDomain>${config.origin}</AppDomain></AppDomains>
  <Hosts><Host Name="Presentation"/></Hosts>
  <DefaultSettings><SourceLocation DefaultValue="${config.origin}/content.html"/><RequestedWidth>960</RequestedWidth><RequestedHeight>540</RequestedHeight></DefaultSettings>
  <Permissions>ReadWriteDocument</Permissions><AllowSnapshot>true</AllowSnapshot>
</OfficeApp>
`;
const unified={
  $schema:'https://developer.microsoft.com/json-schemas/teams/v1.27/MicrosoftTeams.schema.json',manifestVersion:'1.27',version:config.version.split('.').slice(0,3).join('.'),id:config.addinId,
  localizationInfo:{defaultLanguageTag:'en-us'},developer:{name:'Rick PPT',websiteUrl:'https://github.com/dijiahU/rick-ppt',privacyUrl:config.origin+'/privacy.html',termsOfUseUrl:config.origin+'/terms.html'},
  name:{short:'Rick Interactive Runtime',full:'Rick PPT Interactive Slide Runtime'},description:{short:'Interactive teaching inside PowerPoint.',full:'Composable scenes, charts, animation and code labs inside a slide.'},icons:{outline:'icons/icon-32.png',color:'icons/icon-192.png'},accentColor:'#15233B',validDomains:['localhost'],authorization:{permissions:{resourceSpecific:[{name:'Document.ReadWrite.User',type:'Delegated'}]}},
  extensions:[{requirements:{scopes:['presentation'],capabilities:[{name:'PowerPointApi',minVersion:'1.1'}]},contentRuntimes:[{id:'RickContentRuntime',code:{page:config.origin+'/content.html'},requestedWidth:960,requestedHeight:540,disableSnapshot:false}]}]
};
await fs.writeFile(path.join(out,'manifest.addin.xml'),xml);await fs.writeFile(path.join(out,'manifest.unified.json'),JSON.stringify(unified,null,2)+'\n');
// Deterministic simple geometric icons, no external raster dependency.
function crc(bytes){let v=0xffffffff;for(const byte of bytes){v^=byte;for(let j=0;j<8;j++)v=(v>>>1)^((v&1)?0xedb88320:0);}return(v^0xffffffff)>>>0;}
function chunk(type,data){const t=Buffer.from(type),size=Buffer.alloc(4),sum=Buffer.alloc(4);size.writeUInt32BE(data.length);sum.writeUInt32BE(crc(Buffer.concat([t,data])));return Buffer.concat([size,t,data,sum]);}
function icon(n,outline=false){const header=Buffer.alloc(13);header.writeUInt32BE(n);header.writeUInt32BE(n,4);header[8]=8;header[9]=6;const pixels=Buffer.alloc(n*(n*4+1));for(let y=0;y<n;y++)for(let x=0;x<n;x++){const k=y*(n*4+1)+1+x*4;const mark=x>n*.28&&x<n*.72&&y>n*.23&&y<n*.77&&((x<n*.41)||(y<n*.39)||(y>n*.46&&y<n*.59)||(x>n*.52&&y>n*.55));pixels.set(mark?(outline?[255,255,255,255]:[108,231,191,255]):(outline?[0,0,0,0]:[21,35,59,255]),k);}return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',deflateSync(pixels)),chunk('IEND',Buffer.alloc(0))]);}
for(const folder of [path.join(root,'public/icons'),path.join(out,'icons')]){await fs.mkdir(folder,{recursive:true});for(const n of [32,64,192])await fs.writeFile(path.join(folder,`icon-${n}.png`),icon(n,n===32));}
await fs.mkdir(path.join(root,'public'),{recursive:true});
await fs.writeFile(path.join(root,'public/privacy.html'),'<!doctype html><meta charset="utf-8"><title>Local runtime privacy</title><h1>Local runtime privacy</h1><p>Deck scenes and files are served on this computer. The runtime has no analytics. Explicitly allowed data sources can contact their declared origins. Microsoft Office.js is loaded by PowerPoint content pages. Code execution uses isolated, time-limited workers.</p>');
await fs.writeFile(path.join(root,'public/terms.html'),'<!doctype html><meta charset="utf-8"><title>Runtime terms</title><h1>Runtime terms</h1><p>Local development and teaching tool. Source and license: <a href="https://github.com/dijiahU/rick-ppt">Rick PPT</a>. Only install scene plugins you trust.</p>');
console.log(JSON.stringify({addinId:config.addinId,origin:config.origin,manifests:['manifest.addin.xml','manifest.unified.json']}));
