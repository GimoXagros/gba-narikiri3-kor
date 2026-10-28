import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from v13b_small_runtime import apply, bl


class SmallRuntimeGuards(unittest.TestCase):
    def test_rejects_growth_before_assembling(self):
        for size in (0, 0x1000000 - 1, 0x1000000 + 1):
            with self.subTest(size=size), self.assertRaises(ValueError):
                apply(bytes(size), None, None, {})

    def test_immutable_name_and_atlas_guards_before_assembler(self):
        base = bytearray(0x1000000)
        for ident in range(212):
            struct.pack_into('<I', base, 0x1021ac + 56 * ident, 0x08100000)
        cases = []
        changed = bytearray(base)
        struct.pack_into('<I', changed, 0x1021ac, 0x02000000)
        cases.append(('outside pointer', changed))
        changed = bytearray(base)
        changed[0x100000:0x100003] = bytes.fromhex('887f00')
        cases.append(('unmapped Hangul trail', changed))
        changed = bytearray(base)
        changed[0x100000:0x100003] = bytes.fromhex('889f00')
        cases.append(('missing glyph pixels', changed))
        changed = bytearray(base)
        changed[0xfbcc4 + 0x200] = 0x12
        cases.append(('nonuniform blank atlas', changed))
        for label, data in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                # A nonexistent toolchain ensures this rejection must precede
                # any assembler invocation, rather than depend on a real ROM.
                with self.assertRaises(ValueError):
                    apply(data, Path(temporary) / 'missing-toolchain',
                          Path(temporary) / 'output', {})

    def test_clear_bridge_rejects_far_thumb_target(self):
        self.assertEqual(bl(0x080044c8, 0x08001d90), bytes.fromhex('fdf762fc'))
        with self.assertRaises(ValueError):
            bl(0x080044c8, 0x08fbcb9c)


if __name__ == '__main__':
    unittest.main()
