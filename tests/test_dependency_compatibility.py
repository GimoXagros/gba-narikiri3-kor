"""Synthetic tool checks only: no ROM, font asset, gameplay or hardware proof."""
import hashlib
from pathlib import Path
import sys
import unittest

import numpy as np
from fontTools.ttLib import TTFont, newTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_release import apply_writes
from gba_rle import unpack
from intro_graphics_stage import optimal_rle
from menu_readability import inverse, raster


class DependencyCompatibilityTests(unittest.TestCase):
    def test_numpy_owned_writes_preserve_other_bytes(self):
        base = bytes(range(64))
        row = dict(writer='synthetic', offset=4, payload=b'ab', allowed_end=6,
                   expected_sha256=hashlib.sha256(base[4:6]).hexdigest())
        result, ledger = apply_writes(base, [row])
        self.assertEqual(result, base[:4] + b'ab' + base[6:])
        self.assertEqual(ledger[0]['bytes'], 2)
        self.assertEqual(base, bytes(range(64)))
        with self.assertRaisesRegex(ValueError, 'range/overlap'):
            apply_writes(base, [row, row])
        with self.assertRaisesRegex(ValueError, 'source guard'):
            apply_writes(base, [row | {'expected_sha256': '0' * 64}])

    def test_numpy_tile_roundtrip(self):
        raw = bytes(range(256)) * 2
        parts = [(0, 0, 64, 16, 0)]
        pixels = raster(raw, parts)
        self.assertEqual(pixels.dtype, np.dtype('uint8'))
        self.assertEqual(pixels.shape, (16, 64))
        self.assertEqual(inverse(raw, pixels, parts), raw)
        with self.assertRaisesRegex(ValueError, 'bounds'):
            raster(raw[:-1], parts)

    def test_rle_roundtrip(self):
        for raw in (b'a', b'a' * 131, bytes(range(128)), b'abc' * 50):
            with self.subTest(length=len(raw)):
                packed = optimal_rle(raw)
                self.assertEqual(unpack(packed, 0, len(packed), len(raw)), (raw, len(packed)))

    def test_optional_fonttools_name_table(self):
        # No fontTools consumer is currently shipped; check its optional tooling API.
        font = TTFont()
        table = newTable('name')
        table.names = []
        table.setName('합성 글꼴', 1, 3, 1, 0x412)
        restored = newTable('name')
        restored.decompile(table.compile(font), font)
        self.assertEqual(restored.getName(1, 3, 1, 0x412).toUnicode(), '합성 글꼴')


if __name__ == '__main__':
    unittest.main()
