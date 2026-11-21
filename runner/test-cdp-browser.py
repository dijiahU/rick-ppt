"""Offline checks of the dedicated-browser tool boundary (no browser launched)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cdp_browser as cb
from browser_sources import SITE, X


class Tests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.cfg = {'browser_research': {'enabled': True, 'browser': 'edge', 'sites': [SITE, X]}}
        self.tool = cb.BrowseTool(self.cfg, t.name)

    def test_only_https_urls_on_authorized_sites(self):
        sites = [SITE, X]
        self.assertTrue(cb.allowed('https://www.pinterest.com/search/pins/?q=a', sites))
        self.assertTrue(cb.allowed('https://x.com/search?q=a', sites))
        for url in ('http://x.com/', 'https://evil.example/', 'https://x.com.evil.example/', 'file:///etc/hosts'):
            self.assertFalse(cb.allowed(url, sites), url)

    def test_rejected_url_never_starts_a_browser(self):
        with patch.object(cb, 'PipeBrowser') as browser:
            reply = self.tool.handle({'arguments': {'url': 'https://evil.example/'}})
        self.assertFalse(reply['success']); browser.assert_not_called()

    def test_read_returns_text_and_screenshot(self):
        class Fake:
            def __init__(self, headless=True): self.headless = headless
            def read(self, url): return {'title': 'T', 'url': url, 'text': 'hello', 'links': []}, b'\xff\xd8jpeg'
            def close(self): pass
        with patch.object(cb, 'PipeBrowser', Fake):
            reply = self.tool.handle({'arguments': {'url': 'https://x.com/search?q=silk'}})
        self.assertTrue(reply['success'])
        self.assertEqual(json.loads(reply['contentItems'][0]['text'])['text'], 'hello')
        self.assertTrue(reply['contentItems'][1]['imageUrl'].startswith('data:image/jpeg;base64,'))
        saved = json.loads(reply['contentItems'][0]['text'])['screenshot_file']
        self.assertEqual(saved, 'references/browse/1.jpg')
        self.assertEqual((Path(self.tool.job) / saved).read_bytes(), b'\xff\xd8jpeg')

    def test_local_settings_name_only_known_sites(self):
        # One unknown site makes configured_sites() reject the whole list, silently disabling browsing.
        from browser_sources import SITE_HOSTS, configured_sites
        settings = Path(__file__).resolve().parent / 'settings.local.json'
        if settings.is_file():
            cfg = json.loads(settings.read_text())
            sites = (cfg.get('browser_research') or {}).get('sites') or []
            self.assertEqual([s for s in sites if s not in SITE_HOSTS], [])
            if sites:self.assertEqual(configured_sites(cfg), sites)

    def test_profile_lives_outside_the_repository(self):
        self.assertFalse(cb.PROFILE.resolve().is_relative_to(Path(__file__).resolve().parents[1]))


if __name__ == '__main__': unittest.main()
