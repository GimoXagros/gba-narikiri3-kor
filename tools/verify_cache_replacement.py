"""Test replacement at the 124-slot limit using the real two text consumers.

This is a constructed renderer boundary, not a reached whole-game screen.
The old glyph at the destination may be released only if no other cell uses it.
"""
import argparse
import hashlib
import json
from pathlib import Path

from text_codec import encode, hangul_map
from verify_simple_consumer import SimpleFixture


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    rom = a.rom.read_bytes()
    root = Path(__file__).resolve().parents[1]
    glyphs = json.loads((root / 'fonts/dalmoori-wansung.json').read_text(encoding='utf-8'))
    unique, seen = [], set()
    for c in hangul_map().values():
        bitmap = ''.join(glyphs[c])
        if bitmap not in seen:
            unique.append(c)
            seen.add(bitmap)
    coords = [(1 + i % 30, 1 + i // 30) for i in range(124)]
    cases = []
    for mode in (0, 1):
        for consumer in ('window', 'simple'):
            for kind in ('hangul', 'kana'):
                for shared in (False, True):
                    f = SimpleFixture(rom, mode)
                    f.draw(encode(''.join(unique[:124])))
                    before = [f.tile(x, y) for x, y in coords]
                    if shared:
                        f.draw(encode(unique[0]), clear=False, x=20, y=10)
                        alias = f.tile(20, 10)
                    raw = encode(unique[124]) if kind == 'hangul' else b'\xa1'
                    draw = f.draw if consumer == 'window' else f.draw_simple
                    draw(raw, clear=False, x=1, y=1)
                    if shared:
                        # Still 124 other live unique glyphs: genuine exhaustion.
                        expected = f.atlas[0x2f * 32:0x30 * 32]
                    elif kind == 'kana':
                        expected = f.atlas[0x71 * 32:0x72 * 32]
                    else:
                        pixels = [15 if bit == '#' else f.bg for row in glyphs[unique[124]] for bit in row]
                        expected = bytes(pixels[i] | pixels[i + 1] << 4 for i in range(0, 64, 2))
                    unchanged = before[1:] == [f.tile(x, y) for x, y in coords[1:]]
                    alias_ok = not shared or f.tile(20, 10) == alias
                    target_ok = f.tile(1, 1) == expected
                    cases.append({'mode': mode, 'consumer': consumer, 'replacement': kind,
                                  'old_glyph_has_another_reference': shared,
                                  'target_pixels_match': target_ok,
                                  'other_123_glyphs_preserved': unchanged,
                                  'shared_old_glyph_preserved': alias_ok,
                                  'status': 'PASS' if target_ok and unchanged and alias_ok else 'FAIL'})
    failures = [c for c in cases if c['status'] != 'PASS']
    report = {'status': 'FAIL' if failures else 'PASS',
              'rom_sha256': hashlib.sha256(rom).hexdigest(), 'cases': cases,
              'claim': 'Constructed 124-slot replacement boundary through actual Thumb consumers.',
              'limits': ['Not normal-play reachability evidence for a 124-glyph screen.',
                         'True 125-live-glyph exhaustion remains a release condition.',
                         'Does not close font-loader or full-game lifetime coverage.']}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'cases': len(cases), 'failures': len(failures)}))
    if failures:
        raise ValueError('Cache replacement pixels or live references differ')


if __name__ == '__main__':
    main()
