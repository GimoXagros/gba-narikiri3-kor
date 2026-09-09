"""Translate the eight proven symbol tiles of affine inspection resource 440."""
import hashlib
import json
from pathlib import Path
import struct

from gba_rle import unpack, pack_literals

ROOT = Path(__file__).resolve().parents[1]
START, END = 0x111000, 0x115000


def install(legacy, extension, glyphs):
    profile = json.loads((ROOT / 'source/element_symbol_profile.json').read_text('utf-8'))
    catalog = json.loads((ROOT / 'translations/element_symbols.json').read_text('utf-8'))
    if profile['schema'] != 1 or catalog['schema'] != 1 or catalog['policy'] != 'development_only_needs_review':
        raise ValueError('Element symbol source or adoption policy differs')
    bank, entry, source = (int(profile[k], 0) for k in ('bank', 'bank_entry', 'font_offset'))
    if entry != bank + 4 + 282 * 4 or bank + struct.unpack_from('<I', legacy, entry)[0] != source:
        raise ValueError('Inspection font bank linkage differs')
    table = int(profile['affine_resource_table'], 0)
    size = profile['affine_resource_count'] * profile['affine_resource_stride']
    if hashlib.sha256(legacy[table:table + size]).hexdigest() != profile['affine_resource_table_sha256']:
        raise ValueError('Affine resource ownership table differs')
    owners = [i for i in range(86) if struct.unpack_from('<H', legacy, table + i * 8 + 2)[0] == 282]
    if owners != [32] or struct.unpack_from('<4H', legacy, table + 32 * 8) != (440, 282, 283, 284):
        raise ValueError('Inspection font has unexpected typed consumers')
    span = profile['font_stored_span']
    if hashlib.sha256(legacy[source:source + span]).hexdigest() != profile['font_sha256']:
        raise ValueError('Inspection font original bytes differ')
    original, _ = unpack(legacy, source, source + span, profile['font_decoded_bytes'])
    font = bytearray(original)
    rows = {row['id']: row for row in catalog['records']}
    if len(catalog['records']) != 8 or set(rows) != set(range(8)):
        raise ValueError('Element symbol identities differ')
    allowed = set()
    for record in profile['records']:
        row = rows[record['id']]
        if row['source_symbol'] != record['symbol']:
            raise ValueError('Element source symbol does not match its ID')
        char = row['compact']
        if len(char) != 1 or char not in glyphs:
            raise ValueError('Element symbol requires one mapped Hangul glyph')
        tile, code = record['tile'], int(record['byte_code'], 0)
        offset = struct.unpack_from('<h', legacy, 0x7c1938 + code * 2)[0]
        if legacy[0xd882ec + offset] != tile or hashlib.sha256(original[tile * 64:(tile + 1) * 64]).hexdigest() != record['tile_sha256']:
            raise ValueError('Element byte-to-symbol tile selection differs')
        pixels = bytes(0xaf if p == '#' else 0xa1 for line in glyphs[char] for p in line)
        if len(pixels) != 64:
            raise ValueError('Element symbol exceeds its original 8x8 tile')
        font[tile * 64:(tile + 1) * 64] = pixels
        allowed.update(range(tile * 64, (tile + 1) * 64))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(original, font))):
        raise ValueError('Non-symbol inspection graphics changed')
    packed = pack_literals(font)
    if unpack(packed, 0, len(packed), len(font))[0] != font:
        raise ValueError('Inspection graphics RLE round trip differs')
    if START + len(packed) > END or extension[START:END] != b'\xff' * (END - START):
        raise ValueError('Inspection graphics allocation collides')
    extension[START:START + len(packed)] = packed
    return [(entry, struct.pack('<I', 0x1000000 + START - bank),
             'Inspection resource 440: eight Hangul element glyphs; original IDs preserved')], {
                 'symbols': 8, 'font_bank_index': 282, 'decoded_bytes': len(font),
                 'stored_bytes': len(packed), 'start': hex(0x1000000 + START),
                 'end': hex(0x1000000 + START + len(packed)),
                 'scope': profile['scope']}
