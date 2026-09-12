"""Correct the Japanese kig ae / clothing-change label in its existing tiles."""
import hashlib
import json
from pathlib import Path
import struct
from verify_graphics_candidate_edges import decode_stream

ROOT = Path(__file__).resolve().parents[1]


def install(legacy, glyphs):
    p = json.loads((ROOT/'source/costume_label_profile.json').read_text(encoding='utf-8'))
    base = int(p['atlas_offset'], 0)
    if p['korean_label'] != '갈아입기' or p['tiles'] != [384,385,386,387,416,417,418,419]:
        raise ValueError('Unexpected label or tile identity')
    if hashlib.sha256(legacy[base:base+p['atlas_bytes']]).hexdigest() != p['atlas_sha256']:
        raise ValueError('Menu atlas input differs')
    for g in p['guards']:
        at = int(g['offset'],0)
        if legacy[at:at+len(bytes.fromhex(g['hex']))] != bytes.fromhex(g['hex']):
            raise ValueError('Menu loader/layout guard differs')
    owners = {tid:[] for tid in p['tiles']}
    bank = int(p['bank'],0)
    for m in p['maps']:
        at = int(m['offset'],0)
        if bank+struct.unpack_from('<I',legacy,bank+4+4*m['index'])[0] != at:
            raise ValueError('Menu map linkage differs')
        data = legacy[at:at+m['encoded_bytes']]
        if hashlib.sha256(data).hexdigest() != m['sha256']:
            raise ValueError('Menu map source differs')
        decoded, used, _ = decode_stream(data)
        if used != len(data) or len(decoded) != 1280:
            raise ValueError('Menu map extent differs')
        entries = struct.unpack('<640H',decoded)
        for tid in owners:
            owners[tid].extend((m['index'],i) for i,v in enumerate(entries) if v&1023==tid)
    for i,tid in enumerate(p['tiles']):
        if owners[tid] != [(7,(i//4)*32+2+i%4)]:
            raise ValueError('Label tile is shared or moved')
    pixels = []
    for y in range(16):
        tile = p['background_tiles'][y//8]
        row = []
        for x in range(32):
            b = legacy[base+tile*32+(y%8)*4+(x%8)//2]
            row.append((b>>4) if x%2 else (b&15))
        pixels.append(row)
    for i,ch in enumerate(p['korean_label']):
        glyph = glyphs[ch]
        if len(glyph)!=8 or any(len(row)!=8 or set(row)-{'.','#'} for row in glyph):
            raise ValueError('Unverified glyph geometry')
        for y,row in enumerate(glyph):
            for x,bit in enumerate(row):
                if bit=='#':pixels[p['glyph_y']+y][i*8+x]=p['ink_index']
    writes = []
    for i,tid in enumerate(p['tiles']):
        raw = bytearray()
        for y in range(8):
            for x in range(0,8,2):
                line = pixels[(i//4)*8+y]
                raw.append(line[(i%4)*8+x] | line[(i%4)*8+x+1]<<4)
        writes.append((base+tid*32,bytes(raw),'costume-menu label: 갈아입기'))
    return writes, {'text':p['korean_label'], 'japanese':'きがえ', 'existing_tiles':len(writes),
                    'rectangle':[16,0,32,16], 'palette_and_tilemaps_preserved':True}
