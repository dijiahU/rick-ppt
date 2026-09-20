'use client';
import {useEffect,useState} from 'react';
export default function InteractiveDownload({base,locale}:{base:string;locale:string}){
 const zh=locale==='zh-CN';
 const [available,setAvailable]=useState<boolean|null>(null),[error,setError]=useState(false),[retry,setRetry]=useState(0);
 useEffect(()=>{const c=new AbortController();setAvailable(null);setError(false);fetch(`${base}/bundle?info=1`,{cache:'no-store',signal:c.signal}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(v=>setAvailable(!!v&&typeof v==='object'&&'available' in v&&v.available===true)).catch(()=>{if(!c.signal.aborted)setError(true);});return()=>c.abort();},[base,retry]);
 return <section className="room-brief" aria-label={zh?'交互演示下载与使用':'Interactive download and setup'}>
 <h2>{zh?'下载与使用交互演示':'Download and use the interactive presentation'}</h2>
 {error?<p role="alert">{zh?'暂时无法检查交互包。':'Unable to check the interactive package.'} <button onClick={()=>setRetry(n=>n+1)}>{zh?'重试':'Retry'}</button></p>:available===null?<p>{zh?'正在检查完整交互包…':'Checking the complete interactive package…'}</p>:!available?<p>{zh?'此交付没有可下载的交互 ZIP；仍可使用上方的 PPTX 下载。':'This delivery has no interactive ZIP. You can still download the PPTX above.'}</p>:<>
 <p><a className="download" href={`${base}/bundle`}>{zh?'下载完整交互包 ZIP ↓':'Download complete interactive ZIP ↓'}</a></p>
 <p>{zh?'包含 PPTX、交互场景、代码编辑器、运行环境及使用说明。网页里的页面预览是静态图片；单独下载 PPTX 不包含完整交互运行环境。':'Includes the PPTX, scenes, code editor, runtime and setup instructions. Website slide previews are static images; the PPTX alone does not include the complete interactive runtime.'}</p>
 <details><summary>{zh?'如何在浏览器中交互（推荐先体验）':'How to interact in a browser (start here)'}</summary>
 <ol><li>{zh?'解压整个 ZIP，保留文件夹结构。打开其中的 README.txt。':'Extract the entire ZIP, keep its folder structure and open README.txt.'}</li>
 <li>{zh?'安装 Python 3.11 或更新版本。在包含 README.txt 的文件夹中打开终端，执行下方命令。Windows 将 python3 换为 python。':'Install Python 3.11 or later. Open a terminal in the folder containing README.txt and run the commands below. On Windows, replace python3 with python.'}
 <pre style={{overflowX:'auto',whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}><code>{'python3 -m pip install -r scripts/requirements.txt\npython3 scripts/bundle_control.py start --http --port 0'}</code></pre></li>
 <li>{zh?'启动成功后会输出实际的本机网址（url）。复制 README.txt 中的 Standalone preview 完整地址，将开头的 https://localhost:41973 替换为输出的 url；保留后面的 /preview.html?deck=…&scene=…，再在同一台电脑的浏览器打开。自动分配端口可避免端口冲突。':'Startup prints the actual local URL (url). Copy the full Standalone preview address from README.txt, replace its initial https://localhost:41973 with that URL, and retain /preview.html?deck=…&scene=…. Open it in a browser on the same computer. An automatically assigned port avoids conflicts.'}</li>
 <li>{zh?'修改输入或右侧代码后点击 Run / Run inputs 重新计算。有动画的页面使用 Play、Pause、Step 或时间滑块；Reset 恢复初始状态。具体控件以页面为准。':'Change inputs or code, then select Run / Run inputs to recompute. Where provided, use Play, Pause, Step or the timeline slider. Reset restores the initial state.'}</li></ol>
 <p>{zh?'结束后执行：':'When finished, run:'} <code>python3 scripts/bundle_control.py stop</code></p>
 <p>{zh?'若页面显示 404，请检查是否使用了本次启动输出的地址；不要套用其他电脑或旧服务的 localhost 链接。':'If you see a 404, check the URL printed by this startup. Do not reuse localhost links from another computer or an older service.'}</p>
 </details>
 <details><summary>{zh?'如何在 PowerPoint 内交互':'How to interact inside PowerPoint'}</summary>
 <p>{zh?'需要按 README.txt 配置受信任的本地 HTTPS 证书、安装 manifests/manifest.addin.xml 加载项，并启动 HTTPS 运行环境，再打开包内的 presentation.pptx。浏览器 HTTP 模式不能直接用于 PowerPoint 加载项。':'Follow README.txt to configure a trusted local HTTPS certificate, sideload manifests/manifest.addin.xml, start the HTTPS runtime, and open presentation.pptx from the bundle. Browser HTTP mode is not sufficient for the PowerPoint add-in.'}</p>
 <p>{zh?'未配置加载项时可能只显示静态画面。浏览器运行验证不等于已验证你所用 PowerPoint 版本的编辑、放映和保存重开行为；请先在目标电脑试播。':'Without the add-in, you may only see static fallbacks. Browser verification does not certify editing, slideshow or save/reopen behavior in your PowerPoint version; test on the presentation computer first.'}</p>
 </details></>}
 </section>;
}
