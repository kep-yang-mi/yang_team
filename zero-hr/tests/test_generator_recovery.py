"""Regression coverage for truncated entrypoint and standalone source regeneration."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / '.claude/skills/people-data-integration/scripts/generate_synthetic_sources.py'
ARTIFACTS = (
    'data/raw/headcount-master.csv', 'data/raw/to-plan.csv',
    'data/raw/planned-joiners.csv', 'data/raw/planned-leavers.csv',
    'data/raw/injected-defects.json', 'data/reference/org-chart.csv',
    'data/reference/company-stages.json',
)


class TestGeneratorRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='zerohr-recovery-')
        self.root = Path(self.tmp.name)
        # Only the script is copied: no access to an adjacent data/ golden fixture.
        self.script = self.root / 'generate.py'
        shutil.copyfile(GENERATOR, self.script)

    def tearDown(self):
        self.tmp.cleanup()

    def run_generator(self, *options, root=None):
        run = subprocess.run(
            [sys.executable, str(self.script), '--root', str(root or self.root),
             '--as-of', '2026-09-23', *options],
            cwd=self.root, text=True, capture_output=True, timeout=20,
        )
        self.assertTrue(run.stdout.strip(), 'Missing CLI summary: ' + run.stderr)
        return run, json.loads(run.stdout.splitlines()[-1])

    def test_standalone_script_recreates_all_original_sources(self):
        run, summary = self.run_generator('--self-check')
        self.assertEqual(run.returncode, 0, summary)
        self.assertEqual(summary['status'], 'ok')
        self.assertTrue(summary['selfCheck']['passed'])
        for rel in ARTIFACTS:
            self.assertEqual((self.root / rel).read_bytes(), (ROOT / rel).read_bytes(), rel)
        self.assertFalse((self.root / 'data/clean').exists())

    def test_check_only_is_read_only_and_detects_modified_to(self):
        self.run_generator('--self-check')
        before = {rel: ((self.root / rel).read_bytes(), (self.root / rel).stat().st_mtime_ns) for rel in ARTIFACTS}
        run, summary = self.run_generator('--check-only')
        self.assertEqual(run.returncode, 0, summary)
        self.assertTrue(summary['selfCheck']['passed'])
        for rel, expected in before.items():
            path = self.root / rel
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), expected)
        path = self.root / 'data/raw/to-plan.csv'
        changed = path.read_bytes().replace(b'CEO Office,10,', b'CEO Office,11,')
        self.assertNotEqual(changed, path.read_bytes())
        path.write_bytes(changed)
        run, summary = self.run_generator('--check-only')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(summary['status'], 'self-check-failed')
        self.assertFalse(summary['selfCheck']['passed'])
        self.assertEqual(path.read_bytes(), changed)

    def test_check_only_detects_defect_value_corruption(self):
        self.run_generator('--self-check')
        path = self.root / 'data/raw/injected-defects.json'
        defects = json.loads(path.read_text(encoding='utf-8'))
        defects['defects'][0]['rawValue'] = 'corrupted'
        path.write_text(json.dumps(defects, ensure_ascii=False), encoding='utf-8')
        run, summary = self.run_generator('--check-only')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(summary['status'], 'self-check-failed')
        self.assertTrue(any('결함 원천값' in item for item in summary['selfCheck']['failed']))

    def test_no_bom_only_changes_csv_encoding_prefix(self):
        run, summary = self.run_generator('--no-bom', '--self-check')
        self.assertEqual(run.returncode, 0, summary)
        for rel in ARTIFACTS:
            expected = (ROOT / rel).read_bytes()
            if rel.endswith('.csv'):
                self.assertTrue(expected.startswith(b'\xef\xbb\xbf'))
                expected = expected[3:]
            self.assertEqual((self.root / rel).read_bytes(), expected, rel)

    def test_invalid_date_and_missing_inputs_fail_explicitly(self):
        run, summary = self.run_generator('--as-of', 'not-a-date')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(summary['status'], 'error')
        self.assertFalse((self.root / 'data').exists())
        run, summary = self.run_generator('--check-only')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(summary['errorType'], 'FileNotFoundError')
        self.assertFalse((self.root / 'data').exists())


if __name__ == '__main__':
    unittest.main()
