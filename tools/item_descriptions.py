"""Relocate selected proven item descriptions without modifying item behavior."""
import hashlib
import json
from pathlib import Path
import struct

from text_codec import encode

ROOT = Path(__file__).resolve().parents[1]
START, END = 0x120000, 0x130000


def install(legacy, extension):
    profile = json.loads((ROOT / 'source/item_description_profile.json').read_text('utf-8'))
    catalog = json.loads((ROOT / 'translations/item_descriptions.json').read_text('utf-8'))
    if profile['schema'] != 1 or catalog['schema'] != 1 or catalog['policy'] != 'development_only_needs_review':
        raise ValueError('Item description schema or adoption policy differs')
    if hashlib.sha256(legacy[0x105758:0x1062e0]).hexdigest() != profile['legacy_table_sha256']:
        raise ValueError('Original 123-item table differs')
    for guard in profile['guards']:
        at = int(guard['offset'], 0)
        raw = bytes.fromhex(guard['hex'])
        if legacy[at:at + len(raw)] != raw:
            raise ValueError('Original item-description consumer differs')
    if extension[START:END] != b'\xff' * (END - START):
        raise ValueError('Item description pool collision')
    records = {r['id']: r for r in profile['records']}
    selected = catalog['records']
    ids = [r['id'] for r in selected]
    if len(records) != 123 or ids != sorted(set(ids)) or any(i not in records for i in ids):
        raise ValueError('Item-description identities differ')
    writes, cursor = [], START
    for row in selected:
        ident = row['id']
        at = 0x105758 + ident * 24 + 4
        ptr = struct.unpack_from('<I', legacy, at)[0]
        source = ptr - 0x08000000
        record = records[ident]
        if ptr != int(record['pointer'], 0) or hashlib.sha256(legacy[source:legacy.index(0, source) + 1]).hexdigest() != record['legacy_description_sha256']:
            raise ValueError('Item description source differs')
        text = row['text']
        lines = text.split('\n')
        if len(lines) != 2 or any(not 1 <= len(line) <= 18 for line in lines) or '%' in text or any(ord(ch) < 32 and ch != '\n' for ch in text):
            raise ValueError('Item description layout or control differs')
        raw = encode(text) + b'\0'
        if cursor + len(raw) > END:
            raise ValueError('Item description pool overflow')
        extension[cursor:cursor + len(raw)] = raw
        writes.append((at, struct.pack('<I', 0x09000000 + cursor), f'Item {ident}: verified description repair'))
        cursor += len(raw)
    return writes, {'reviewed_typed_records': 123, 'selected_description_fields': len(selected),
                    'start': hex(0x1000000 + START), 'end': hex(0x1000000 + cursor),
                    'scope': profile['scope']}
