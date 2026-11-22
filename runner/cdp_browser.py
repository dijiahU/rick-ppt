"""A dedicated, logged-in Edge driven directly over the DevTools protocol (pipe mode).

No browser extension and no network port: the host launches Edge with
--remote-debugging-pipe and its own profile directory, so commands return in
milliseconds instead of waiting on the extension's tab attachment. The tool only
reads: open a URL, return visible text, links and one screenshot.
"""
import base64
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import shutil
import sys


def find_browser():
    """Edge (or Chrome) on macOS/Linux; PPTX_BROWSER_EXECUTABLE overrides."""
    override = os.environ.get('PPTX_BROWSER_EXECUTABLE')
    if override:
        return override
    known = ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
             '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    for name in ('microsoft-edge', 'microsoft-edge-stable', 'google-chrome', 'chromium'):
        found = shutil.which(name)
        if found:
            known.append(found)
    return next((p for p in known if Path(p).is_file()), known[0])


EDGE = find_browser()
# Outside the repository: it holds the operator's site cookies and must never be committed.
PROFILE = Path.home() / '.rick-ppt' / 'edge-profile'
TOOL = 'pptx_browse'
VIEWPORT = (1366, 900)

READ_PAGE = '''(() => {
  const text = (document.body ? document.body.innerText : '').replace(/\\n{3,}/g, '\\n\\n').slice(0, 8000);
  const seen = new Set(); const links = [];
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href; const label = (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
    if (!href.startsWith('http') || seen.has(href) || label.length < 2) continue;
    seen.add(href); links.push({text: label.slice(0, 120), href});
    if (links.length >= 40) break;
  }
  const images = [...document.images].filter(i => i.naturalWidth >= 150 && /^https:\/\/i\.pinimg\.com\//.test(i.currentSrc || i.src))
    .map(i => ({src: i.currentSrc || i.src, alt: (i.alt || '').slice(0, 160), pin: (i.closest('a') || {}).href || null})).slice(0, 24);
  return {title: document.title, url: location.href, text, links, images};
})()'''


class CdpError(RuntimeError):
    pass


class PipeBrowser:
    """Minimal CDP client over Edge's --remote-debugging-pipe (NUL-separated JSON)."""

    def __init__(self, profile=PROFILE, executable=EDGE, headless=True):
        self.profile = Path(profile); self.executable = executable; self.headless = headless
        self.proc = None; self.next_id = 0; self.lock = threading.Lock()
        self.buffer = b''; self.pending_events = []

    def start(self):
        if self.proc and self.proc.poll() is None:
            return
        if sys.platform == 'win32':
            raise CdpError('Browser research uses --remote-debugging-pipe, which needs macOS/Linux; built-in web search still works')
        if not Path(self.executable).is_file():
            raise CdpError('Microsoft Edge or Chrome is not installed (or set PPTX_BROWSER_EXECUTABLE)')
        self.profile.mkdir(parents=True, exist_ok=True)
        to_browser_r, self.to_browser = os.pipe()
        self.from_browser, from_browser_w = os.pipe()
        def wire():  # Edge reads commands on fd 3 and writes replies on fd 4.
            r, w = os.dup(to_browser_r), os.dup(from_browser_w)  # move clear of 3/4 first
            os.dup2(r, 3); os.dup2(w, 4)
        args = [self.executable, '--remote-debugging-pipe', f'--user-data-dir={self.profile}', '--no-first-run',
                '--no-default-browser-check', '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
                f'--window-size={VIEWPORT[0]},{VIEWPORT[1]}']
        if self.headless:
            args.append('--headless=new')
        self.proc = subprocess.Popen(args + ['about:blank'], preexec_fn=wire, pass_fds=(3, 4, to_browser_r, from_browser_w),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        os.close(to_browser_r); os.close(from_browser_w)
        try:
            self.call('Browser.getVersion', timeout=20)
        except CdpError:
            if (self.profile / 'SingletonLock').is_symlink():
                raise CdpError('The dedicated Edge profile is open in another window; close that window and retry')
            raise

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.call('Browser.close', timeout=5)
            except Exception:
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for fd in ('to_browser', 'from_browser'):
            try:
                os.close(getattr(self, fd))
            except (OSError, AttributeError):
                pass
        self.proc = None

    def _read_message(self, deadline):
        import select
        while b'\0' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CdpError('DevTools reply timed out')
            ready, _, _ = select.select([self.from_browser], [], [], remaining)
            if not ready:
                continue
            chunk = os.read(self.from_browser, 1 << 20)
            if not chunk:
                raise CdpError('Edge closed the DevTools pipe')
            self.buffer += chunk
        message, self.buffer = self.buffer.split(b'\0', 1)
        return json.loads(message)

    def call(self, method, params=None, *, session=None, timeout=30):
        with self.lock:
            self.next_id += 1; ident = self.next_id
            message = {'id': ident, 'method': method, 'params': params or {}}
            if session:
                message['sessionId'] = session
            os.write(self.to_browser, json.dumps(message).encode() + b'\0')
            deadline = time.monotonic() + timeout
            while True:
                reply = self._read_message(deadline)
                if reply.get('id') == ident:
                    if 'error' in reply:
                        raise CdpError(f"{method}: {reply['error'].get('message')}")
                    return reply.get('result', {})
                self.pending_events.append(reply)
                del self.pending_events[:-200]

    def wait_event(self, method, session, timeout):
        deadline = time.monotonic() + timeout
        with self.lock:
            while time.monotonic() < deadline:
                for event in self.pending_events:
                    if event.get('method') == method and event.get('sessionId') == session:
                        self.pending_events.remove(event); return True
                try:
                    event = self._read_message(min(deadline, time.monotonic() + 0.5))
                except CdpError as error:
                    if 'timed out' in str(error):
                        continue
                    raise
                if event.get('method') == method and event.get('sessionId') == session:
                    return True
                self.pending_events.append(event)
        return False

    def read(self, url, *, settle=1.0, max_settle=6.0, load_timeout=8):
        """Open url in a fresh tab, return (page data, JPEG screenshot bytes), close the tab."""
        self.start()
        target = self.call('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = self.call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        try:
            self.call('Page.enable', session=session)
            self.call('Emulation.setDeviceMetricsOverride', {'width': VIEWPORT[0], 'height': VIEWPORT[1],
                      'deviceScaleFactor': 1, 'mobile': False}, session=session)
            self.call('Page.navigate', {'url': url}, session=session)
            # Feeds keep loading forever; the document plus a short settle is enough to read results.
            self.wait_event('Page.domContentEventFired', session, load_timeout)
            # Result lists render after the document: wait until text and loaded images stop growing.
            probe = ('(() => [document.body ? document.body.innerText.length : 0, '
                     '[...document.images].filter(i => i.complete && i.naturalWidth > 80).length])()')
            last, stable, deadline = None, 0, time.monotonic() + max_settle
            time.sleep(settle)
            while time.monotonic() < deadline:
                now = (self.call('Runtime.evaluate', {'expression': probe, 'returnByValue': True},
                                 session=session).get('result') or {}).get('value')
                stable = stable + 1 if now == last and now and now[0] > 200 else 0
                if stable >= 2:
                    break
                last = now; time.sleep(0.5)
            data = self.call('Runtime.evaluate', {'expression': READ_PAGE, 'returnByValue': True}, session=session)
            value = (data.get('result') or {}).get('value') or {}
            shot = self.call('Page.captureScreenshot', {'format': 'jpeg', 'quality': 70}, session=session)
            return value, base64.b64decode(shot['data'])
        finally:
            try:
                self.call('Target.closeTarget', {'targetId': target}, timeout=5)
            except CdpError:
                pass


def allowed(url, sites):
    host = (urlsplit(url).hostname or '').lower()
    return urlsplit(url).scheme == 'https' and any(
        host == (urlsplit(s).hostname or '') or host.endswith('.' + (urlsplit(s).hostname or '').removeprefix('www.'))
        for s in sites)


# Concurrent jobs run as threads of one worker and the dedicated profile admits one Edge.
# Each tool used to launch its own Edge, so a second job failed with "profile is open in
# another window" (2026-11-21: two parallel jobs lost all Pinterest research). Share one.
_SHARED = {}
_SHARED_LOCK = threading.Lock()
_READ_LOCK = threading.Lock()


def shared_browser(headless):
    with _SHARED_LOCK:
        browser = _SHARED.get(headless)
        if browser is None:
            browser = _SHARED[headless] = PipeBrowser(headless=headless)
        return browser


class BrowseTool:
    """Host tool for the research/author agent: read one logged-in page quickly."""

    def __init__(self, cfg, job, *, trajectory=None):
        from browser_sources import configured_sites
        self.sites = configured_sites(cfg); self.job = Path(job)
        self.headless = cfg['browser_research'].get('headless', True) is not False
        self.trajectory = trajectory; self.browser = None

    def specs(self):
        return [{'type': 'function', 'name': TOOL, 'description': (
            'Read a page in the operator\'s logged-in Edge (dedicated profile) for sites built-in search cannot reach: '
            + ', '.join(self.sites) + '. Pass a full https URL, e.g. a site search URL. Returns the visible text, up to '
            '40 links and a screenshot (also saved under references/browse/ so it can be registered as a reference), in a '
            'few seconds. Read only; screenshots are references, not assets.'),
            'inputSchema': {'type': 'object', 'additionalProperties': False, 'required': ['url'], 'properties': {
                'url': {'type': 'string', 'description': 'Full https URL on an allowed site.'},
                'save_images': {'type': 'integer', 'minimum': 0, 'maximum': 8,
                                'description': 'Pinterest pages: also save this many result images at full size under '
                                               'references/pinterest/ to inspect closely and register as references.'}}}}]

    def handle(self, params):
        url = (params.get('arguments') or {}).get('url')
        if not isinstance(url, str) or not allowed(url, self.sites):
            return {'success': False, 'contentItems': [{'type': 'inputText', 'text':
                    'Use a full https URL on: ' + ', '.join(self.sites)}]}
        started = time.monotonic()
        try:
            if self.browser is None:
                # headless=false shows a normal Edge window, for sites that refuse headless browsers.
                self.browser = shared_browser(self.headless)
            with _READ_LOCK:  # one page at a time on the shared browser
                page, shot = self.browser.read(url)
        except (CdpError, OSError) as error:
            return {'success': False, 'contentItems': [{'type': 'inputText', 'text': f'Browser read failed: {error}'}]}
        wanted = (params.get('arguments') or {}).get('save_images') or 0
        page['saved_images'] = self._save_pins(page.pop('images', []), wanted) if wanted else []
        folder = self.job / 'references' / 'browse'
        folder.mkdir(parents=True, exist_ok=True)
        saved = folder / f'{len(list(folder.glob("*.jpg"))) + 1}.jpg'
        saved.write_bytes(shot)
        page['screenshot_file'] = str(saved.relative_to(self.job))
        from trajectory import record
        record(self.trajectory, 'emit', 'browse.read', {'url': url, 'seconds': round(time.monotonic() - started, 1),
                                                        'chars': len(page.get('text') or ''), 'file': page['screenshot_file']})
        return {'success': True, 'contentItems': [
            {'type': 'inputText', 'text': json.dumps(page, ensure_ascii=False)},
            {'type': 'inputImage', 'imageUrl': 'data:image/jpeg;base64,' + base64.b64encode(shot).decode()}]}

    def _save_pins(self, images, count):
        """Download full-size Pinterest images (public CDN) as references; rights stay with the creators."""
        import re
        import urllib.request
        folder = self.job / 'references' / 'pinterest'
        folder.mkdir(parents=True, exist_ok=True)
        saved = []
        for item in images:
            if len(saved) >= count:
                break
            src = re.sub(r'^https://i\.pinimg\.com/[^/]+/', 'https://i.pinimg.com/originals/', item['src'])
            for url in (src, item['src']):
                try:
                    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(request, timeout=15) as response:
                        data = response.read(15 * 1024 * 1024)
                    if data[:3] == b'\xff\xd8\xff' or data[:8] == b'\x89PNG\r\n\x1a\n' or data[8:12] == b'WEBP':
                        from PIL import Image
                        import io
                        with Image.open(io.BytesIO(data)) as im:
                            if max(im.size) < 500:
                                continue  # a thumbnail is too small to study; try the next candidate
                        suffix = '.png' if data[:4] == b'\x89PNG' else '.jpg'
                        target = folder / (str(len(list(folder.iterdir())) + 1) + suffix)
                        target.write_bytes(data)
                        saved.append({'file': str(target.relative_to(self.job)), 'alt': item['alt'], 'source': url,
                                      'pin': item.get('pin')})
                        break
                except OSError:
                    continue
        return saved

    def close(self):
        # The shared browser outlives one job; it is released when the worker exits.
        self.browser = None


def login(sites):
    """Open the dedicated profile visibly so the operator can sign in once."""
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([EDGE, f'--user-data-dir={PROFILE}', '--no-first-run', '--no-default-browser-check', *sites])


if __name__ == '__main__':
    import sys
    if sys.argv[1:2] == ['login']:
        login(['https://x.com', 'https://www.pinterest.com'])
        print('Sign in to the opened sites, then close that Edge window.')
    elif sys.argv[1:2] == ['read']:
        b = PipeBrowser()
        try:
            t = time.monotonic(); page, shot = b.read(sys.argv[2])
            print(round(time.monotonic() - t, 1), 's', page.get('title'), len(page.get('text') or ''), 'chars',
                  len(page.get('links') or []), 'links', len(shot), 'bytes jpeg')
            if len(sys.argv) > 3:
                Path(sys.argv[3]).write_bytes(shot)
        finally:
            b.close()
