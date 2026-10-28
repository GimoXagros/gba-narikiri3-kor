import sys
import hashlib
import struct
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from v13b_changes import apply_profiles, build_text
from v13b_preservation import verify
from v13b_small_ui import bl, build as build_small_ui
from v13_fixes import thumb_bl
from v13b_numeric_prefix import apply as apply_numeric_prefix


class OverlayGuards(unittest.TestCase):
    def test_numeric_prefix_rejects_occupied_slots_before_assembling(self):
        base = bytearray(16777216)
        base[0xccb80:0xccb88] = bytes.fromhex('00b50a1c092a05dc')
        for start, size in ((0xfbcf64, 156), (0xfbbee0, 144)):
            base[start:start+size] = b'\xff'*size
        for at in (0xccb80, 0xfbcf64, 0xfbbee0):
            changed = bytearray(base)
            changed[at] ^= 1
            with self.subTest(at=at), self.assertRaises(ValueError):
                apply_numeric_prefix(bytes(changed), None, None)

    def test_small_ui_requires_current_linked_cache_symbols(self):
        for symbols in ({}, {'row_cached_tile': 0x08fbbf70},
                        {'small_composite': 0x08fbc06c}):
            with self.subTest(symbols=symbols), self.assertRaises(TypeError):
                build_small_ui(None, None, None, 0x08fbc15c, **symbols)

    def test_thumb_calls_preserve_targets_and_reject_far_or_odd_targets(self):
        site = 0x080044c8
        for encode in (bl, thumb_bl):
            for delta in (-0x400000, -2, 0, 2, 0x3ffffe):
                target = site + 4 + delta
                hi, lo = struct.unpack('<HH', encode(site, target))
                offset = ((hi & 0x7ff) << 12) | ((lo & 0x7ff) << 1)
                if offset & 0x400000:
                    offset -= 0x800000
                self.assertEqual(site + 4 + offset, target)
            for target in (0x08fbcb9c, site + 4 + 0x400000,
                           site + 4 - 0x400002, site + 5):
                with self.subTest(encoder=encode.__name__, target=target), self.assertRaises((ValueError, AssertionError)):
                    encode(site, target)

    def test_final_layer_preservation_rejects_mutation(self):
        base = bytearray(16777216)
        base[20:24] = b'abc\0'
        base = bytes(base)
        metadata = dict(baseline_sha256=hashlib.sha256(base).hexdigest(),
                        strings=[dict(offset=20, length=3, pointer_fields=[4])],
                        unchanged_regions=[dict(start=100, end=104, label='keyboard')], scope='test')
        self.assertEqual(verify(base, base, metadata)['pointer_fields'], 1)
        for at in (4, 20, 21, 23, 100):
            changed = bytearray(base)
            changed[at] = 0 if at == 21 else 1
            with self.subTest(at=at), self.assertRaises(ValueError):
                verify(base, bytes(changed), metadata)
        with self.assertRaises(ValueError):
            verify(base, base+b'\0', metadata)

    def test_identical_aliases_share_fixed_bytes(self):
        row = dict(offset=1, expected_hex='8140', payload_hex='1601')
        self.assertEqual(apply_profiles(b'A\x81\x40B', [{'writes': [row, row]}]), b'A\x16\x01B')

    def test_rejects_conflicts_source_and_bounds(self):
        row = dict(offset=1, expected_hex='8140', payload_hex='1601')
        for rows in ([row, row | {'payload_hex': '1602'}],
                     [row | {'offset': -1}], [row | {'offset': 3}],
                     [row | {'expected_hex': '2020'}], [row | {'payload_hex': '17'}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                apply_profiles(b'A\x81\x40B', [{'writes': rows}])
        with self.assertRaises(ValueError):
            build_text(bytes(16777216))


if __name__ == '__main__':
    unittest.main()
