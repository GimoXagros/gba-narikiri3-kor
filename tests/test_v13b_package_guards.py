import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_v13a_package import JP, verify_checksums, verify_metadata


class PackageGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def checksum_fixture(self, version='1.3b'):
        names = [f'ND3_B3TJ_K_v{version}_FROM_J.bps', f'ND3_Korean_v{version}.zip',
                 f'v{version}-release-manifest.json']
        lines = []
        for name in names:
            data = name.encode('ascii')
            (self.root/name).write_bytes(data)
            lines.append(hashlib.sha256(data).hexdigest() + '  ' + name)
        path = self.root/f'v{version}-SHA256SUMS.txt'
        path.write_text('\n'.join(lines) + '\n', 'ascii')
        return path, lines

    def metadata_fixture(self, version='1.3b'):
        patch = f'ND3_B3TJ_K_v{version}_FROM_J.bps'
        inner = dict(version=version, source_sha256=JP, source_size=0x1000000,
                     target_sha256='a'*64, target_size=0x1000000, patch_sha256='b'*64,
                     patch_file=patch, status='RELEASE_READY', source_commit='c'*40,
                     gates={'preservation': 'PASS'}, gate_details={'hardware': {'agent_hardware_execution': 'NOT_RUN'}})
        outer = copy.deepcopy(inner)
        outer.update(zip_file=f'ND3_Korean_v{version}.zip', zip_sha256='d'*64,
                     zip_bytes=100, members={}, public_assets=[patch, f'ND3_Korean_v{version}.zip',
                     f'v{version}-release-manifest.json', f'v{version}-SHA256SUMS.txt'])
        return inner, outer

    def test_valid_v13a_and_v13b_compatibility(self):
        for version in ('1.3a', '1.3b'):
            with self.subTest(version=version):
                self.checksum_fixture(version)
                verify_checksums(self.root, version)
                inner, outer = self.metadata_fixture(version)
                verify_metadata(inner, outer, version, 'a'*64, 'b'*64)

    def test_checksum_completeness_and_duplicates(self):
        path, lines = self.checksum_fixture()
        for content in ('', '\n'.join(lines[:2]), '\n'.join(lines+[lines[0]]),
                        '\n'.join([lines[0], lines[0], lines[2]])):
            with self.subTest(content=content), self.assertRaises(ValueError):
                path.write_text(content, 'ascii')
                verify_checksums(self.root, '1.3b')

    def test_checksum_digest_syntax_and_content(self):
        path, lines = self.checksum_fixture()
        for bad in ('0'*64 + lines[0][64:], 'z'*64 + lines[0][64:],
                    lines[0][1:], lines[0].replace('  ', ' ', 1),
                    lines[0][:66] + '../escape', ''):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                path.write_text('\n'.join([bad, *lines[1:]]) + '\n', 'ascii')
                verify_checksums(self.root, '1.3b')

    def test_shared_fields_must_match_even_for_nested_gate_details(self):
        inner, outer = self.metadata_fixture()
        for key, value in inner.items():
            changed = copy.deepcopy(outer)
            changed[key] = {'mismatch': True} if isinstance(value, dict) else 'mismatch'
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_metadata(inner, changed, '1.3b', 'a'*64, 'b'*64)

    def test_agreeing_manifests_still_require_profile_identity(self):
        for key, wrong in dict(version='1.3a', source_sha256='0'*64, source_size=1,
                               target_sha256='0'*64, target_size=1,
                               patch_sha256='0'*64, patch_file='wrong.bps').items():
            inner, outer = self.metadata_fixture()
            inner[key] = outer[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_metadata(inner, outer, '1.3b', 'a'*64, 'b'*64)
        inner, outer = self.metadata_fixture()
        for target, patch in [('0'*64, 'b'*64), ('a'*64, '0'*64)]:
            with self.assertRaises(ValueError):
                verify_metadata(inner, outer, '1.3b', target, patch)

    def test_missing_extra_or_renamed_public_metadata_rejected(self):
        inner, outer = self.metadata_fixture()
        variants = []
        missing = copy.deepcopy(outer)
        del missing['source_commit']
        variants.append(missing)
        variants.append(outer | {'unexpected': True})
        variants.append(outer | {'zip_file': 'wrong.zip'})
        variants.append(outer | {'public_assets': outer['public_assets'][:-1]})
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                verify_metadata(inner, changed, '1.3b', 'a'*64, 'b'*64)

    def test_external_member_inventory_is_exact(self):
        inner, outer = self.metadata_fixture()
        expected = {'manifest.json', inner['patch_file']}
        outer['members'] = {name: {} for name in expected}
        verify_metadata(inner, outer, '1.3b', 'a'*64, 'b'*64, expected)
        for members in ({}, outer['members'] | {'extra.bin': {}}, list(expected)):
            with self.subTest(members=members), self.assertRaises(ValueError):
                verify_metadata(inner, outer | {'members': members}, '1.3b', 'a'*64, 'b'*64, expected)


if __name__ == '__main__':
    unittest.main()
