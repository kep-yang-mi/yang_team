"""The site frame preserves deep links and the dashboard's source data."""
import json
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / 'site'


class TestWorkspace(unittest.TestCase):
    def test_navigation_targets_are_sections_in_one_document(self):
        home = (SITE / 'index.html').read_text()
        nav = re.search(r'<nav class="workspace-nav".*?</nav>', home, re.S)[0]
        destinations = re.findall(r'href="([^"]+)"', nav)
        self.assertEqual(len(destinations), 8)
        self.assertEqual(home.count('aria-current="page"'), 1)
        self.assertIn('src="/assets/workspace.js"', home)
        self.assertIn('https://claude.ai/code/artifact/7e13938a-4161-4a07-b4be-d010dc6f33cb', destinations)
        for url in destinations:
            if url.startswith('https://'):
                continue
            self.assertTrue(url.startswith('/#'), url)
            self.assertIn('id="{}"'.format(url[2:]), home, url)

    def test_home_uses_complete_dashboard_data(self):
        def snapshot(path):
            source = path.read_text()
            return json.loads(re.search(r'<script id="report-data"[^>]*>(.*?)</script>', source, re.S)[1])
        self.assertEqual(snapshot(SITE / 'index.html'), snapshot(SITE / 'app/index.html'))
        self.assertNotIn('src="../', (SITE / 'index.html').read_text())

    def test_email_report_keeps_original_format(self):
        self.assertNotIn('workspace-sidebar', (SITE.parent / 'reports/monthly-report-2026-10.html').read_text())
