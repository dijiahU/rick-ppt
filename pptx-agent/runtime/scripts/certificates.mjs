// Use Microsoft's generator without its uninstall/delete-on-renew path.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {generateCertificates} from 'office-addin-dev-certs';
const dir=path.join(os.homedir(),'.office-addin-dev-certs');
const paths=['ca.crt','localhost.crt','localhost.key'].map(name=>path.join(dir,name));
const exists=await Promise.all(paths.map(file=>fs.access(file).then(()=>true,()=>false)));
if(exists.some(Boolean)&&!exists.every(Boolean))throw Error('An incomplete certificate set exists. Preserved without modification. Choose a separate certificate directory manually.');
if(!exists.some(Boolean)){
 await fs.mkdir(dir,{recursive:true,mode:0o700});
 await generateCertificates(...paths,365,['localhost','127.0.0.1']);
 await fs.chmod(paths[2],0o600);
}
if(process.platform==='darwin'){
 // User trust only; leave the system keychain and other certificates unchanged.
 execFileSync('security',['add-trusted-cert','-r','trustRoot','-k',path.join(os.homedir(),'Library/Keychains/login.keychain-db'),paths[0]],{timeout:20000,stdio:'pipe'});
 execFileSync('security',['verify-cert','-c',paths[1],'-p','ssl','-s','localhost'],{timeout:10000,stdio:'pipe'});
}else if(process.platform==='win32'){
 execFileSync('certutil',['-user','-addstore','Root',paths[0]],{timeout:20000,stdio:'pipe'});
}else{
 console.log(JSON.stringify({generated:true,trusted:false,message:'Import ca.crt into the browser/OS trust store, then verify HTTPS. Files were preserved.'}));process.exit(0);
}
console.log(JSON.stringify({generated:true,trusted:true,scope:'current-user',days:365}));
