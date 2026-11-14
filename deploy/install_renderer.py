"""Verify and extract the pinned official renderer without changing system Office."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


def install(archive,destination):
    lock=json.loads(Path(__file__).with_name('libreoffice-renderer.lock.json').read_text())
    sha=hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):sha.update(chunk)
    if sha.hexdigest()!=lock['sha256']:raise ValueError('Official renderer archive checksum mismatch')
    destination=destination.absolute()
    if destination.exists():raise ValueError('Installation destination already exists; retain it unchanged')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.renderer-install-',dir=destination.parent) as temporary:
        stage=Path(temporary);debs=stage/'debs';debs.mkdir();payload=stage/'payload';payload.mkdir()
        with tarfile.open(archive,'r:gz') as bundle:
            packages=[m for m in bundle.getmembers() if m.isfile() and m.name.endswith('.deb')]
            if not 1<=len(packages)<=200 or sum(m.size for m in packages)>2*1024**3:
                raise ValueError('Unexpected renderer package inventory')
            names=set()
            for member in packages:
                name=Path(member.name).name
                if name in names:raise ValueError('Duplicate renderer package')
                names.add(name)
                with bundle.extractfile(member) as source,(debs/name).open('xb') as target:
                    shutil.copyfileobj(source,target,1024*1024)
        for package in sorted(debs.iterdir()):
            subprocess.run(['dpkg-deb','--extract',str(package),str(payload)],check=True,
                           env={**os.environ,'DPKG_DEB_THREADS_MAX':'1'},stdout=subprocess.DEVNULL)
        prefixes=[p for p in (payload/'opt').glob('libreoffice*') if (p/'program/soffice.bin').is_file()]
        if len(prefixes)!=1:raise ValueError('Renderer prefix is ambiguous')
        prefix=prefixes[0]
        receipt={**lock,'page_range_verified':False,'packages':len(packages)}
        (prefix/'share/rick-ppt-renderer.json').write_text(json.dumps(receipt,indent=2))
        relative=prefix.relative_to(payload)
        os.replace(payload,destination);destination.chmod(0o755)
    return {'version':lock['version'],'prefix':str(destination/relative),'sha256':lock['sha256'],
            'page_range_verified':False,'activated':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(install(args.archive,args.destination)))
