"""Adopted V3 intro renderer and five immutable-source Expected Writes.

No bitmap/font assets are bundled: foreground comes from the identified local
baseline. This is the bounded graphics stage, not full proofread completion.
"""
import hashlib
import json
import struct
from pathlib import Path

import numpy as np

from gba_rle import unpack
from text_codec import encode, glyph_index

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def optimal_rle(blob):
    """Deterministic minimal BIOS type-30 stream; literals win cost ties."""
    if not blob or len(blob) > 0xffffff:
        raise ValueError('Invalid BIOS RLE payload size')
    n = len(blob)
    cost, actions = [0] * (n + 1), [None] * (n + 1)
    for i in range(n - 1, -1, -1):
        best = (10**9, None)
        for length in range(1, min(128, n - i) + 1):
            candidate = 1 + length + cost[i + length]
            if candidate < best[0]:
                best = (candidate, ('literal', length))
        run = 1
        while run < min(130, n - i) and blob[i + run] == blob[i]:
            run += 1
        for length in range(3, run + 1):
            candidate = 2 + cost[i + length]
            if candidate < best[0]:
                best = (candidate, ('run', length))
        cost[i], actions[i] = best
    result = bytearray(struct.pack('<I', (n << 8) | 0x30))
    i = 0
    while i < n:
        kind, length = actions[i]
        if kind == 'literal':
            result.append(length - 1)
            result.extend(blob[i:i + length])
        else:
            result.extend((0x80 | (length - 3), blob[i]))
        i += length
    return bytes(result)


def pack_pixels(pixels):
    result = bytearray(6144)
    for y in range(64):
        for x in range(192):
            at = ((x // 64) * 64 + (y // 8) * 8 + (x % 64) // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            result[at] |= pixels[y][x] << (4 * (x % 2))
    return bytes(result)


def render_card(base, profile, card):
    pixels = [[0] * 192 for _ in range(64)]
    foreground, outline = set(), set()
    instances, shared_outline = 0, 0
    if ' '.join(card['ko_rom_lines']) != card['ko_readable'].replace('\n', ' '):
        raise ValueError('Layout changes readable words or spaces')
    if len(card['ko_rom_lines']) != len(card['line_y']):
        raise ValueError('Line placement count differs')
    for line, y in zip(card['ko_rom_lines'], card['line_y'], strict=True):
        width = sum(4 if c in ' ,.' else 12 for c in line)
        x = (192 - width) // 2
        for char in line:
            if char != ' ':
                raw = encode(char)
                if len(raw) == 1:
                    raw = {'.': '。', ',': '、'}[char].encode('cp932')
                slot = glyph_index(int.from_bytes(raw, 'big'))
                at = int(profile['large_font_offset'], 0) + slot * 32
                glyph = base[at:at + 32]
                adopted = profile['glyphs'][char]
                if slot != adopted['large_font_slot'] or sha(glyph) != adopted['source_12x16_sha256']:
                    raise ValueError(f'Source glyph identity differs: {char}')
                rows = struct.unpack('<16H', glyph)
                if any(rows[12:]) or any(bits >> 12 for bits in rows):
                    raise ValueError(f'Crop would delete ink: {char}')
                local = {(dx, dy) for dy in range(12) for dx in range(12) if rows[dy] & (1 << dx)}
                ink = {(x + dx, y + dy) for dx, dy in local}
                edge = {(gx + dx, gy + dy) for gx, gy in ink for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))}
                edge -= ink
                if ink & foreground or ink & outline or edge & foreground:
                    raise ValueError(f'Ink overlaps another glyph: {char}')
                if any(not (0 < gx < 191 and 0 < gy < 63) for gx, gy in ink | edge):
                    raise ValueError(f'Ink/outline clipping: {char}')
                shared_outline += len(edge & outline)
                foreground |= ink
                outline |= edge
                for gx, gy in edge:
                    pixels[gy][gx] = 1
                for gx, gy in ink:
                    pixels[gy][gx] = 4
                instances += 1
            x += 4 if char in ' ,.' else 12
    if {(x, y) for y in range(64) for x in range(192) if pixels[y][x] == 4} != foreground:
        raise ValueError('Source foreground was altered')
    decoded = pack_pixels(pixels)
    packed = optimal_rle(decoded)
    if sha(decoded) != card['decoded_sha256'] or sha(packed) != card['payload_sha256'] or len(packed) != card['payload_bytes']:
        raise ValueError('Renderer differs from frozen V3 proposal')
    if unpack(packed, 0, len(packed), 6144) != (decoded, len(packed)):
        raise ValueError('Intro compression roundtrip differs')
    return packed, {'card': card['card'], 'glyph_instances': instances, 'foreground_overlap': 0,
                    'source_ink_deletion': 0, 'shared_outline_pixels': shared_outline,
                    'decoded_sha256': sha(decoded), 'packed_sha256': sha(packed)}


def plan(base, japanese, profile):
    if profile['schema'] != 1 or profile['revision'] != 'UNIFORM_FAITHFUL12X12_CROP_V3':
        raise ValueError('Unsupported adopted graphics profile')
    if sha(base) != profile['baseline_sha256'] or len(base) != profile['baseline_bytes']:
        raise ValueError('Immutable graphics-stage baseline differs')
    if sha(japanese) != profile['japanese_sha256'] or len(japanese) != 0x1000000:
        raise ValueError('Immutable Japanese input differs')
    fs, fe = (int(profile[k], 0) for k in ('large_font_offset', 'large_font_end'))
    if sha(base[fs:fe]) != profile['large_font_sha256']:
        raise ValueError('Protected inherited large font differs')
    writes, render_reports = [], []
    for card in profile['cards']:
        at, end = int(card['rom_offset'], 0), int(card['allocation_end'], 0)
        if sha(base[at:end]) != card['allocation_sha256']:
            raise ValueError('Entire intro allocation baseline differs')
        if unpack(japanese, at, end, 6144)[1] != end:
            raise ValueError('Japanese original consumed allocation differs')
        packed, report = render_card(base, profile, card)
        if at + len(packed) > end:
            raise ValueError('Intro resource exceeds proven original allocation')
        writes.append({'writer': card['source_id'], 'offset': at, 'allowed_end': end,
                       'expected_sha256': sha(base[at:at + len(packed)]), 'payload': packed})
        render_reports.append(report)
    element = profile['element']
    ep = json.loads((ROOT / element['profile']).read_text('utf-8'))
    bank, entry, font = (int(ep[k], 0) for k in ('bank', 'bank_entry', 'font_offset'))
    if element['fields'] != ['attack', 'resistance', 'weakness'] or element['id8'] != 'original blank' or not element['user_authorized']:
        raise ValueError('Original shared element policy differs')
    if base[entry:entry + 4].hex() != element['expected_before_hex']:
        raise ValueError('Element immutable pointer source differs')
    original = base[font:font + ep['font_stored_span']]
    if sha(original) != ep['font_sha256'] or original != japanese[font:font + len(original)]:
        raise ValueError('Preserved original symbol resource differs')
    payload = struct.pack('<I', font - bank)
    if payload.hex() != element['payload_hex']:
        raise ValueError('Element pointer address basis differs')
    writes.append({'writer': 'original-elements-resource440', 'offset': entry, 'allowed_end': entry + 4,
                   'expected_sha256': sha(base[entry:entry + 4]), 'payload': payload})
    prior_end = 0
    for write in sorted(writes, key=lambda w: w['offset']):
        start, end = write['offset'], write['offset'] + len(write['payload'])
        if start < prior_end or end > write['allowed_end'] or end > len(base):
            raise ValueError('Overlapping or out-of-range Expected Writes')
        if sha(base[start:end]) != write['expected_sha256']:
            raise ValueError('Immutable Expected Write guard failed')
        prior_end = end
    for protected in profile['protected_ranges']:
        at, end = int(protected['start'], 0), int(protected['end'], 0)
        if sha(base[at:end]) != protected['sha256']:
            raise ValueError('Protected baseline range differs')
        if any(w['offset'] < end and at < w['offset'] + len(w['payload']) for w in writes):
            raise ValueError('Write intersects protected range')
    return writes, render_reports


def build(base, japanese, profile):
    writes, reports = plan(base, japanese, profile)
    result = bytearray(base)
    allowed = np.zeros(len(base), dtype=np.bool_)
    for w in writes:
        at, payload = w['offset'], w['payload']
        result[at:at + len(payload)] = payload
        allowed[at:at + len(payload)] = True
    output = bytes(result)
    changed = np.frombuffer(base, np.uint8) != np.frombuffer(output, np.uint8)
    if len(output) != len(base) or np.any(changed & ~allowed):
        raise ValueError('Unexplained final diff or size change')
    for p in profile['protected_ranges']:
        at, end = int(p['start'], 0), int(p['end'], 0)
        if output[at:end] != base[at:end]:
            raise ValueError('Protected output range changed')
    return output, {'status': 'GRAPHICS_STAGE_CONTROL_STATIC_PASS_RUNTIME_SEPARATE',
                    'baseline_sha256': sha(base), 'japanese_sha256': sha(japanese),
                    'rom_sha256': sha(output), 'rom_bytes': len(output),
                    'changed_bytes': int(changed.sum()), 'unexplained_changed_bytes': 0,
                    'writes': [{**{k: v for k, v in w.items() if k != 'payload'},
                                'byte_count': len(w['payload']), 'payload_sha256': sha(w['payload'])} for w in writes],
                    'render_reports': reports, 'strict_in_place_intro_objects': 4,
                    'intro_pointer_values_changed': 0, 'element_bank_fields_changed': 1,
                    'language_proposals_integrated': 0, 'existing_25_tone_changes': 'PRESERVED_BY_EXACT_DIFF',
                    'limits': ['Intermediate graphics control, not the final full-language candidate.',
                               'Original 16MiB placement and natural Inspect Eye gameplay remain separate.']}
