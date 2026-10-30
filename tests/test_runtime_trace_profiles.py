import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_runtime_smoke import sha, timing_reference


class RuntimeTraceProfiles(unittest.TestCase):
    def check_exact_identity_and_rejection(self, version):
        records = json.loads((ROOT / 'source/opening_timing_profile.json').read_text(encoding='utf8'))['records']
        baseline = json.loads((ROOT / f'qa/traces/{version}-first-save.json').read_text('utf8'))['candidate_sha256']
        rows = [r for r in records if r.get('reload_trace_sha256') and r['rom_sha256'] == baseline]
        self.assertEqual(len(rows), 2)
        for row in rows:
            values = [row[k] for k in ('rom_sha256', 'core_sha256', 'trace_sha256')]
            self.assertEqual(timing_reference(*values, required=True), row)
            self.assertEqual(row['trace_sha256'], sha(ROOT / f'qa/traces/{version}-first-save.json'))
            self.assertEqual(row['reload_trace_sha256'], sha(ROOT / f'qa/traces/{version}-reload-menu.json'))
            for i in range(3):
                changed = values.copy()
                changed[i] = '0' * 64
                with self.assertRaises(ValueError):
                    timing_reference(*changed, required=True)

    def test_v13a_exact_identity_and_rejection(self):
        self.check_exact_identity_and_rejection("v13a")

    def test_v13b_exact_identity_and_rejection(self):
        self.check_exact_identity_and_rejection("v13b")

    def test_legacy_unknown_identity_keeps_existing_fallback(self):
        self.assertIsNone(timing_reference('unknown', 'unknown', 'unknown'))


if __name__ == '__main__':
    unittest.main()
