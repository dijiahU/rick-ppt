"""Loopback-only runtime server. Standalone HTTP is explicit; Office uses trusted TLS."""
from __future__ import annotations
import argparse
import asyncio
import json
import secrets
import ssl
from pathlib import Path
from urllib.parse import urlsplit
from aiohttp import web
from .common import PptxError
from .interactive_validate import PLUGIN_ROOT,config,safe_path,read_json


def certificate_paths():
    root=Path.home()/'.office-addin-dev-certs'
    return root/'localhost.crt',root/'localhost.key'


def tls_context(cert=None,key=None):
    default_cert,default_key=certificate_paths()
    cert=Path(cert) if cert else default_cert;key=Path(key) if key else default_key
    if not cert.is_file() or not key.is_file():raise PptxError('Trusted localhost certificate missing. Run pptx interactive cert install.')
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(cert,key);return ctx


def create_app(root, runtime=None, allowlist=()):
    root=Path(root).resolve();runtime=Path(runtime or PLUGIN_ROOT/'runtime/dist').resolve();cfg=config();tokens={}
    deck_dirs={}
    if (root/'deck/bundle.json').is_file():
        info=read_json(root/'deck/bundle.json');deck_dirs[info['deckId']]=root/'deck'
    elif (root/'bundle.json').is_file():
        info=read_json(root/'bundle.json');deck_dirs[info['deckId']]=root
    for folder in (root/'decks').glob('*') if (root/'decks').is_dir() else []:
        if not folder.is_symlink() and (folder/'bundle.json').is_file():deck_dirs[read_json(folder/'bundle.json')['deckId']]=folder
    origins=set(allowlist)
    for folder in deck_dirs.values():
        bundle=read_json(folder/'bundle.json')
        for scene in bundle.get('scenes',{}).values():
            spec=read_json(safe_path(folder,scene['path']))
            for origin in spec.get('runtimeOptions',{}).get('networkAllowlist',[]):
                u=urlsplit(origin)
                if u.scheme not in ('https','wss') or u.path not in ('','/') or u.query or u.fragment or u.username:raise PptxError('Invalid network origin')
                origins.add(origin)
    @web.middleware
    async def headers(request,handler):
        host=urlsplit('http://'+request.host).hostname
        if host not in ('localhost','127.0.0.1','::1'):raise web.HTTPForbidden(text='Loopback Host required')
        try:response=await handler(request)
        except web.HTTPException as error:response=web.Response(status=error.status,text=error.text,headers=error.headers)
        office=' https://appsforoffice.microsoft.com' if request.path.endswith('content.html') else ''
        response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; script-src 'self' blob: 'wasm-unsafe-eval'"+office+"; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data: "+' '.join(origins)+"; media-src 'self' blob:; connect-src 'self' "+' '.join(origins)+"; font-src 'self'; worker-src 'self' blob:; frame-src 'self' blob:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self' https://*.office.com https://*.officeapps.live.com https://*.microsoft365.com"})
        if request.path=='/packs/code/code-runner.worker.js':
            response.headers['Content-Security-Policy']="default-src 'none'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; connect-src 'self'; worker-src 'none'; object-src 'none'"
        if request.path.startswith('/icons/'):
            response.headers['Cache-Control']='public, max-age=3600'
        return response
    app=web.Application(middlewares=[headers],client_max_size=1024*1024)
    def check_origin(request):
        origin=request.headers.get('Origin')
        if origin and origin!=f'{request.scheme}://{request.host}':raise web.HTTPForbidden(text='Cross-origin request denied')
    async def health(request):return web.json_response({'ok':True,'runtimeVersion':cfg['runtimeVersion'],'decks':list(deck_dirs)})
    async def session(request):
        check_origin(request);deck=request.match_info['deck']
        if deck not in deck_dirs:raise web.HTTPNotFound()
        tokens[deck]=secrets.token_urlsafe(32);return web.json_response({'nonce':tokens[deck]})
    async def websocket(request):
        check_origin(request);deck=request.match_info['deck'];token=request.query.get('nonce','')
        if deck not in tokens or not secrets.compare_digest(tokens[deck],token):raise web.HTTPForbidden()
        ws=web.WebSocketResponse(max_msg_size=65536,heartbeat=30);await ws.prepare(request)
        async for msg in ws:
            if msg.type==web.WSMsgType.TEXT:
                try:
                    value=json.loads(msg.data)
                    if value.get('type')!='ping':await ws.send_json({'error':'Only deck-scoped ping is supported'})
                    else:await ws.send_json({'type':'pong','deckId':deck})
                except ValueError:await ws.close(code=1007)
        return ws
    async def asset(request):
        try:
            path=request.match_info.get('path','') or 'preview.html'
            if path.startswith('decks/'):
                _,deck,relative=path.split('/',2)
                if deck not in deck_dirs:raise PptxError('Unknown deck')
                target=safe_path(deck_dirs[deck],relative)
            elif path.startswith('source/'):
                target=safe_path(root,path.removeprefix('source/'))
                if target.suffix.lower() not in {'.json','.csv','.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm','.wav','.mp3','.onnx','.glb','.gltf','.bin'}:raise PptxError('Source type not served')
            else:target=safe_path(runtime,path)
            if target.stat().st_size>1024*1024*1024:raise PptxError('Asset too large')
            return web.FileResponse(target)
        except (PptxError,ValueError,OSError):raise web.HTTPNotFound()
    app.router.add_get('/api/health',health);app.router.add_get('/api/session/{deck}',session);app.router.add_get('/api/ws/{deck}',websocket);app.router.add_get('/{path:.*}',asset)
    return app


async def start_server(root,runtime=None,port=0,tls=False,cert=None,key=None):
    runner=web.AppRunner(create_app(root,runtime));await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',port,ssl_context=tls_context(cert,key) if tls else None);await site.start()
    actual=site._server.sockets[0].getsockname()[1]
    return runner, f'{"https" if tls else "http"}://{"localhost" if tls else "127.0.0.1"}:{actual}'


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--runtime');p.add_argument('--port',type=int,default=config()['port']);p.add_argument('--http',action='store_true');p.add_argument('--cert');p.add_argument('--key');a=p.parse_args(argv)
    async def serve():
        runner,url=await start_server(a.root,a.runtime,a.port,not a.http,a.cert,a.key)
        print(json.dumps({'url':url,'pid':__import__('os').getpid(),'officeHTTPS':not a.http}),flush=True)
        try:await asyncio.Event().wait()
        finally:await runner.cleanup()
    asyncio.run(serve())

if __name__=='__main__':main()
