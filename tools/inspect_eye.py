"""Install the dedicated affine battle-inspection text renderer."""
import hashlib
import json
from pathlib import Path
import struct

from text_codec import encode

ROOT = Path(__file__).resolve().parents[1]


def install(legacy, extension, code):
    profile = json.loads((ROOT / 'source/inspect_eye_profile.json').read_text('utf-8'))
    catalog = json.loads((ROOT / 'translations/inspect_eye.json').read_text('utf-8'))
    if profile['schema'] != 1 or catalog['policy'] != 'development_only_needs_review':
        raise ValueError('Inspection translation policy differs')
    for guard in profile['guards']:
        off = int(guard['offset'], 0)
        raw = bytes.fromhex(guard['hex'])
        if legacy[off:off + len(raw)] != raw:
            raise ValueError('Inspection consumer/resource setup differs')
    for resource in profile['protected_resources']:
        off = int(resource['offset'], 0)
        raw = legacy[off:off + resource['size']]
        if hashlib.sha256(raw).hexdigest() != resource['sha256']:
            raise ValueError('Inspection atlas, palette or map differs')
    names = json.loads((ROOT / 'translations/items-monsters.json').read_text('utf-8'))['groups']['monster']
    if len(names) != 212 or any(len(row['compact']) > 9 for row in names):
        raise ValueError('Inspection title exceeds its nine position slots')
    if len(code) > 0x600 or extension[0xa00:0x1000] != b'\xff' * 0x600:
        raise ValueError('Inspection code/font allocation collision')
    if extension[0x110000:0x111000] != b'\xff' * 0x1000:
        raise ValueError('Inspection label allocation collision')
    extension[0xa00:0xa00 + len(code)] = code
    writes = [(0x16a48, bytes.fromhex('004b1847') + struct.pack('<I', 0x09000a01),
               'Inspection affine text: complete Korean glyphs in unused 8bpp slots')]
    rows = {row['id']: row['text'] for row in catalog['records']}
    if set(rows) != {row['id'] for row in profile['records']}:
        raise ValueError('Inspection label identities differ')
    cursor = 0x110000
    for row in profile['records']:
        pointer = int(row['pointer_offset'], 0)
        old = struct.unpack_from('<I', legacy, pointer)[0] - 0x08000000
        raw = bytes.fromhex(row['original_hex'])
        if legacy[old:old + len(raw)] != raw:
            raise ValueError('Inspection original label differs')
        text = rows[row['id']]
        if len(text) != 3 or text[-1] != ':' or any(not '\uac00' <= c <= '\ud7a3' for c in text[:2]):
            raise ValueError('Inspection label must be two Hangul cells and colon')
        encoded = encode(text) + b'\0'
        extension[cursor:cursor + len(encoded)] = encoded
        writes.append((pointer, struct.pack('<I', 0x09000000 + cursor),
                       'Inspection label: ' + text))
        cursor += len(encoded)
    return writes, {'labels': 3, 'monster_titles': 212, 'code_size': len(code),
                    'code_start': '0x1000a00', 'label_start': '0x1110000', 'label_end': hex(0x1000000 + cursor),
                    'new_vram_tiles': [240, 254], 'vram_bytes': ['0x0600bc00', '0x0600bfbf'],
                    'persistent_ram_bytes': 0, 'scope': profile['scope']}
