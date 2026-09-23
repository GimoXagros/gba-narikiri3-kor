"""Relocate reviewed monster-library descriptions through proven +4 fields."""
import hashlib
import json
from pathlib import Path
import struct

from text_codec import encode

ROOT = Path(__file__).resolve().parents[1]
BASE, COUNT, STRIDE, FIELD = 0x1be848, 212, 8, 4
START, END = 0x150000, 0x160000  # Relative to the existing 16-MiB extension.


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_string(rom, pointer):
    offset = pointer - 0x08000000
    if not 0 <= offset < len(rom):
        raise ValueError('Monster description data pointer is outside the ROM')
    end = rom.find(b'\0', offset)
    if end < 0:
        raise ValueError('Unterminated monster description')
    return rom[offset:end + 1]


def validate_sources(japanese, legacy):
    profile = json.loads((ROOT / 'source/monster_description_profile.json').read_text('utf-8'))
    catalog = json.loads((ROOT / 'translations/monster_descriptions.json').read_text('utf-8'))
    if profile['schema'] != 1 or catalog['schema'] != 1 or catalog['policy'] != 'development_only_needs_review':
        raise ValueError('Monster description schema or adoption policy differs')
    if (int(profile['table'], 0), profile['count'], profile['stride'], profile['description_field']) != (BASE, COUNT, STRIDE, FIELD):
        raise ValueError('Monster description record layout differs')
    if (int(profile['extension_start'], 0), int(profile['extension_end'], 0)) != (START, END):
        raise ValueError('Monster description allocation differs')
    for label, rom in [('japanese', japanese), ('legacy', legacy)]:
        if len(rom) != 0x1000000 or sha(rom) != profile[label + '_rom_sha256']:
            raise ValueError('Unsupported monster description source ROM')
        if sha(rom[BASE:BASE + COUNT * STRIDE]) != profile[label + '_table_sha256']:
            raise ValueError('Monster description source table differs')
        for guard in profile['guards']:
            at, raw = int(guard['offset'], 0), bytes.fromhex(guard['hex'])
            if rom[at:at + len(raw)] != raw:
                raise ValueError('Monster description consumer guard differs')
    if [r['id'] for r in profile['records']] != list(range(COUNT)):
        raise ValueError('Monster description profile population differs')
    for i, row in enumerate(profile['records']):
        at = BASE + i * STRIDE
        if int(row['pointer_offset'], 0) != at + FIELD:
            raise ValueError('Monster description pointer field differs')
        for label, rom in [('japanese', japanese), ('legacy', legacy)]:
            if rom[at:at + FIELD].hex() != row['metadata_hex']:
                raise ValueError('Monster library non-pointer metadata differs')
            expected = struct.pack('<I', int(row[label + '_pointer'], 0))
            if rom[at + FIELD:at + STRIDE] != expected:
                raise ValueError('Monster description original pointer bytes differ')
            raw = source_string(rom, int(row[label + '_pointer'], 0))
            if raw.hex() != row[label + '_raw'] or sha(raw) != row[label + '_description_sha256']:
                raise ValueError('Monster description source content or terminator differs')
    ids = [r['id'] for r in catalog['records']]
    if ids != sorted(set(ids)) or any(not isinstance(i, int) or not 0 <= i < COUNT for i in ids):
        raise ValueError('Monster description selected identities differ')
    for row in catalog['records']:
        text = row['text']
        lines = text.split('\n')
        if not 1 <= len(lines) <= 2 or any(not 1 <= len(line) <= 18 for line in lines):
            raise ValueError('Monster description exceeds two 18-cell lines')
        if any(c in text for c in ('%', '@')) or any(ord(c) < 32 and c != '\n' for c in text):
            raise ValueError('Unmodeled monster description control')
        encode(text)
    return profile, catalog


def install(japanese, legacy, extension):
    """Return pointer writes after validating every input; mutate only own pool."""
    profile, catalog = validate_sources(japanese, legacy)
    if len(extension) < END or extension[START:END] != b'\xff' * (END - START):
        raise ValueError('Monster description extension pool collision')
    writes, allocations, details, cursor = [], [], [], START
    # Validate and prepare the complete plan before applying any pool bytes.
    for row in catalog['records']:
        ident, text = row['id'], row['text']
        at = BASE + ident * STRIDE + FIELD
        raw = encode(text) + b'\0'
        if cursor + len(raw) > END:
            raise ValueError('Monster description extension pool overflow')
        target = 0x09000000 + cursor
        replacement = struct.pack('<I', target)
        writes.append((at, replacement, f'Monster library {ident}: reviewed description'))
        allocations.append((cursor, raw))
        details.append({'id': ident, 'stable_id': row.get('stable_id'), 'pointer_offset': hex(at),
                        'expected_original_hex': legacy[at:at + 4].hex(),
                        'original_target': profile['records'][ident]['legacy_pointer'],
                        'new_target': hex(target), 'replacement_hex': replacement.hex(),
                        'target_rom_offset': hex(target - 0x08000000), 'stored_bytes': len(raw),
                        'content_sha256': sha(raw), 'kind': 'plain_data_pointer'})
        cursor += len(raw)  # Data addresses retain low bits; no Thumb tagging.
    if len({at for at, _, _ in writes}) != len(writes):
        raise ValueError('Overlapping monster description pointer writes')
    for at, raw in allocations:
        extension[at:at + len(raw)] = raw
    return writes, {'reviewed_typed_records': COUNT, 'selected_description_fields': len(writes),
                    'start': hex(0x1000000 + START), 'end': hex(0x1000000 + cursor),
                    'japanese_rom_sha256': sha(japanese), 'legacy_rom_sha256': sha(legacy),
                    'plain_data_pointer_writes': details, 'scope': profile['scope']}
