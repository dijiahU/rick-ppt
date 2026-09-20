"""Create a new CNN local handoff; never alter the delivered original."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
from urllib.parse import urlencode
from lxml import etree as E
P='http://schemas.openxmlformats.org/presentationml/2006/main';A='http://schemas.openxmlformats.org/drawingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';REL='http://schemas.openxmlformats.org/package/2006/relationships';ns={'p':P,'a':A}
def build(source,destination,python):
    destination.mkdir(parents=True,exist_ok=False)
    root=destination/'运行文件';shutil.copytree(source,root)
    bundle=json.loads((root/'deck/bundle.json').read_text());deckid=bundle['deckId']
    scenes=sorted(bundle['scenes']);assert len(scenes)==20
    original=(source/'presentation.pptx')
    with zipfile.ZipFile(original) as src,zipfile.ZipFile(root/'presentation.pptx','w',zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            body=src.read(item.filename)
            for n,scene in enumerate(scenes,1):
                if item.filename==f'ppt/slides/slide{n}.xml':
                    x=E.fromstring(body)
                    matches=[s for s in x.findall('.//p:sp',ns) if 'Experiment • change an input' in ''.join(s.xpath('.//a:t/text()',namespaces=ns))]
                    assert len(matches)==1
                    sp=matches[0];c=sp.find('p:nvSpPr/p:cNvPr',ns)
                    c.set('name','Open interactive lab');c.set('descr','Open this slide experiment in your browser; Command Tab returns to PowerPoint.')
                    E.SubElement(c,'{'+A+'}hlinkClick',{'{'+R+'}id':'rIdLocalInteractive','tooltip':'Open this slide’s local interactive experiment'})
                    props=sp.find('p:spPr',ns);props.find('a:xfrm/a:ext',ns).set('cy','365760')
                    for fill in props.findall('a:noFill',ns)+props.findall('a:solidFill',ns):props.remove(fill)
                    fill=E.SubElement(props,'{'+A+'}solidFill');E.SubElement(fill,'{'+A+'}srgbClr',val='087E8B')
                    tx=sp.find('p:txBody',ns)
                    for child in list(tx):tx.remove(child)
                    E.SubElement(tx,'{'+A+'}bodyPr',anchor='ctr',lIns='91440',rIns='91440',tIns='0',bIns='0');E.SubElement(tx,'{'+A+'}lstStyle')
                    para=E.SubElement(tx,'{'+A+'}p');E.SubElement(para,'{'+A+'}pPr',algn='ctr')
                    run=E.SubElement(para,'{'+A+'}r');rp=E.SubElement(run,'{'+A+'}rPr',lang='en-US',sz='1600',b='1')
                    f=E.SubElement(rp,'{'+A+'}solidFill');E.SubElement(f,'{'+A+'}srgbClr',val='FFFFFF');E.SubElement(rp,'{'+A+'}latin',typeface='Arial')
                    E.SubElement(run,'{'+A+'}t').text='OPEN INTERACTIVE LAB  ↗  ·  Return with ⌘ Tab'
                    body=E.tostring(x,xml_declaration=True,encoding='UTF-8',standalone=True)
                elif item.filename==f'ppt/slides/_rels/slide{n}.xml.rels':
                    x=E.fromstring(body)
                    E.SubElement(x,'{'+REL+'}Relationship',Id='rIdLocalInteractive',Type=R+'/hyperlink',Target='http://127.0.0.1:1/preview.html?'+urlencode({'deck':deckid,'scene':scene}),TargetMode='External')
                    body=E.tostring(x,xml_declaration=True,encoding='UTF-8',standalone=True)
            out.writestr(item,body)
    shutil.copy2(Path(__file__).with_name('launch.py'),root/'launch.py')
    (root/'local-python.txt').write_text(str(python))
    # The immutable source bundle remains untouched; this new distribution has its own hashes.
    bundle['pptxHash']=hashlib.sha256((root/'presentation.pptx').read_bytes()).hexdigest()
    (root/'deck/bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
    links=''.join(f'<li><a href="preview.html?{urlencode({"deck":deckid,"scene":s})}">第 {n} 页 · {s[7:]}</a></li>' for n,s in enumerate(scenes,1))
    (root/'runtime/dist/local-guide.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CNN 本地演示</title><style>body{font:20px system-ui;max-width:900px;margin:48px auto;padding:24px;line-height:1.7;color:#183044}a{color:#087e8b}li{margin:8px 0}ol{columns:2}h1{font-size:36px}</style><h1>CNN 已准备好，可以开始放映</h1><p>PowerPoint 中打开的是本次启动生成的放映文件。每页右侧实验图下方都有绿色 <b>OPEN INTERACTIVE LAB ↗</b> 按钮。</p><p>① 放映 PPT → ② 点击绿色按钮进入对应实验 → ③ Run inputs 计算，Play / Step 演示 → ④ 按 <b>⌘ Tab</b> 返回刚才的 PPT 页面。</p><p>修改代码后需要重新 Run。Reset 恢复初始状态。编辑视图如果点击仅选中按钮，请先进入放映模式再点击。</p><p>演示期间保持本机运行环境启动。下次使用请重新双击启动入口，并使用新打开的放映文件，不要沿用旧端口的文件。浏览器实验与 PPT 翻页、保存不会自动同步。</p><h2>也可以直接选择实验</h2><ol>'''+links+'</ol></html>')
    readme='''CNN 本地可用版（Mac）\n\n1. 双击「开始演示.command」。它会自动启动本机播放器、选择空闲端口，并打开使用指南和 PowerPoint。无需网站、账号、HTTPS 证书或 Office 加载项。\n2. 在自动打开的 PowerPoint 中开始放映。每页右侧实验图片下方有绿色 OPEN INTERACTIVE LAB 按钮，点击进入本页实验。\n3. 在浏览器点 Run inputs；有动画时点 Play / Pause / Step。改代码后重新 Run，Reset 恢复。按 Command + Tab 返回 PowerPoint，继续原来的页面。\n4. 演示结束双击「结束演示.command」。它只停止本交付包启动的播放器。\n\n每次启动都会在「本次放映」文件夹创建一个新的 PPTX，不覆盖以前的文件。请用本次自动打开的文件；旧文件里的端口可能已失效。\n「运行文件/presentation.pptx」是生成用模板，不要直接拿它放映。不要移动或拆散运行文件里的内容。\n如果 macOS 首次询问是否打开下载的脚本，可在 Finder 中右键脚本选择打开；不要关闭系统安全保护。\n此包使用这台 Mac 已安装的 Python 环境。搬到另一台电脑需 Python 3.11+ 和 scripts/requirements.txt 中依赖，可用 PPTX_PYTHON 指定解释器。\n交互结果在浏览器显示，不会自动写回 PPT。要保留改过的代码，请自行复制保存；Reset 会恢复初始代码。\n'''
    (destination/'先读我.txt').write_text(readme)
    for name,args in [('开始演示.command',''),('结束演示.command','--stop')]:
        script='''#!/bin/sh\nset -eu\nHERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nPY=${PPTX_PYTHON:-$(cat "$HERE/运行文件/local-python.txt")}\nif [ ! -x "$PY" ]; then PY=$(command -v python3.11 || command -v python3); fi\nif ! "$PY" "$HERE/运行文件/launch.py" '''+args+'''; then\n  echo "启动失败。请保留上方错误信息；无需删除任何文件。"\n  read -r ANSWER\n  exit 1\nfi\n'''
        p=destination/name;p.write_text(script);p.chmod(0o755)
    hashes={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and p.name!='checksums.json' and '__pycache__' not in p.parts}
    (root/'checksums.json').write_text(json.dumps(hashes,indent=2))
    print(destination)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('destination',type=Path);p.add_argument('--python',required=True,type=Path);a=p.parse_args();build(a.source,a.destination,a.python)
