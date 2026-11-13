"""Run the existing media decoder under the Linux task boundary."""
import os,runpy,sys
from pathlib import Path
from linux_sandbox import restrict
root=Path(sys.argv[1]).resolve(strict=True)
decoder=Path(__file__).resolve().parents[1]/'runner/media-container/normalize.py'
restrict(root,reads=[str(decoder)])
os.environ['PPTX_MEDIA_ROOT']=str(root)
runpy.run_path(str(decoder),run_name='__main__')
