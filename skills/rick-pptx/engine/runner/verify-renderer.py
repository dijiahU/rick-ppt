"""Verify PageRange inside the production renderer sandbox before activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from pptx import Presentation
from pptx.util import Inches

ROOT=Path(__file__).resolve().parents[1]


def verify(prefix):
    prefix=prefix.resolve(strict=True)
    manifest=prefix/'share/rick-ppt-renderer.json'
    receipt=json.loads(manifest.read_text())
    with tempfile.TemporaryDirectory(prefix='pptx-r-capability-') as temporary:
        root=Path(temporary);(root/'output').mkdir()
        deck=Presentation()
        for text in ('PPTX_PAGE_ONE','PPTX_PAGE_TWO'):
            slide=deck.slides.add_slide(deck.slide_layouts[6])
            slide.shapes.add_textbox(Inches(1),Inches(1),Inches(7),Inches(2)).text=text
        deck.save(root/'input.pptx')
        shutil.copyfile(ROOT/'deploy/office_tmp.so',root/'office_tmp.so')
        (root/'fonts.conf').write_text('<?xml version="1.0"?><fontconfig><include>/etc/fonts/fonts.conf</include><cachedir>'+str(root/'cache')+'</cachedir></fontconfig>')
        code='''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[3]);sys.path.insert(0,sys.argv[4])
from linux_sandbox import restrict
from linux_render import office_command,convert,fresh_profile,render_parallelism
root=Path(sys.argv[1]);prefix=Path(sys.argv[2])
command=office_command(root,'input.pptx',2,prefix=prefix);parallelism=render_parallelism()
restrict(root,reads=[str(prefix),'/var/lib/libreoffice','/var/spool/libreoffice','/var/cache/fontconfig'],local_socket_server=True)
os.environ.update(LD_PRELOAD=str(root/'office_tmp.so'),URE_BOOTSTRAP='vnd.sun.star.pathname:'+str(prefix/'program/fundamentalrc'),SAL_USE_VCLPLUGIN='svp',MAX_CONCURRENCY=str(parallelism))
raise SystemExit(convert(command,interrupted_retry=fresh_profile).returncode)
'''
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(root),'TMPDIR':str(root),
             'OSL_SOCKET_PATH':str(root),'FONTCONFIG_FILE':str(root/'fonts.conf')}
        started=time.monotonic()
        process=subprocess.Popen([sys.executable,'-c',code,str(root),str(prefix),str(ROOT/'deploy'),str(ROOT/'runner')],
                                 env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            stdout,stderr=process.communicate(timeout=120)
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL);process.communicate()
        if process.returncode:raise RuntimeError('Isolated capability probe failed: '+stderr[-1000:])
        pdf=root/'output/input.pdf'
        info=subprocess.check_output(['pdfinfo',str(pdf)],text=True,env={**env,'LC_ALL':'C'},timeout=20)
        pages=int(next(line.split(':',1)[1] for line in info.splitlines() if line.startswith('Pages:')))
        text=subprocess.check_output(['pdftotext',str(pdf),'-'],text=True,env=env,timeout=20)
        if pages!=1 or 'PPTX_PAGE_TWO' not in text or 'PPTX_PAGE_ONE' in text:
            raise RuntimeError('PageRange did not export exactly the requested page')
        proof={'input_pages':2,'requested_page':2,'pdf_pages':pages,
               'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
               'elapsed_seconds':round(time.monotonic()-started,4)}
    receipt.update(page_range_verified=True,page_range_probe=proof)
    fd,temporary=tempfile.mkstemp(prefix='.renderer-proof-',dir=manifest.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
        os.chmod(temporary,0o644);os.replace(temporary,manifest)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return {'page_range_verified':True,'prefix':str(prefix),**proof}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prefix',type=Path,required=True)
    print(json.dumps(verify(parser.parse_args().prefix)))
