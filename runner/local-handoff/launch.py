"""Start a verified bundle and produce a session PPTX with actual local URLs."""
from pathlib import Path
import argparse,datetime,json,subprocess,sys,uuid,zipfile
from urllib.parse import urlsplit,urlunsplit
from lxml import etree as ET
ROOT=Path(__file__).resolve().parent

def materialize(source,destination,origin):
    parsed=urlsplit(origin)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or not parsed.port:
        raise ValueError('Expected a local runtime URL')
    count=0
    with zipfile.ZipFile(source) as src,zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            body=src.read(item.filename)
            if item.filename.startswith('ppt/slides/_rels/') and item.filename.endswith('.rels'):
                xml=ET.fromstring(body)
                for rel in xml:
                    if rel.get('Id')=='rIdLocalInteractive':
                        target=urlsplit(rel.get('Target'))
                        rel.set('Target',urlunsplit((parsed.scheme,parsed.netloc,target.path,target.query,'')))
                        count+=1
                body=ET.tostring(xml,xml_declaration=True,encoding='UTF-8',standalone=True)
            out.writestr(item,body)
    if count!=20:raise ValueError(f'Expected 20 slide links, got {count}')
    return count

def main():
    p=argparse.ArgumentParser();p.add_argument('--no-open',action='store_true');p.add_argument('--stop',action='store_true');args=p.parse_args()
    controller=ROOT/'scripts/bundle_control.py'
    if args.stop:
        subprocess.run([sys.executable,str(controller),'stop'],check=True);return
    result=subprocess.run([sys.executable,str(controller),'start','--http','--port','0'],check=True,capture_output=True,text=True)
    state=json.loads(result.stdout);origin=state['url']
    # Session copies are outside the immutable/checksummed runtime folder.
    output=ROOT.parent/'本次放映';output.mkdir(exist_ok=True)
    deck=output/('CNN-点击放映-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.pptx')
    materialize(ROOT/'presentation.pptx',deck,origin)
    print(json.dumps({'pptx':str(deck),'guide':origin+'/local-guide.html','running':state['running']},ensure_ascii=False),flush=True)
    if not args.no_open:
        if sys.platform=='darwin':
            subprocess.run(['open',origin+'/local-guide.html'],check=True)
            subprocess.run(['open','-a','Microsoft PowerPoint',str(deck)],check=True)
        else:print('Open the PPTX above and use its OPEN INTERACTIVE LAB buttons.')
if __name__=='__main__':main()
