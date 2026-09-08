"""Four typed sprite resources for the two established skill-screen headers."""
import hashlib,json,struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
START=0xc0000
END=0xc1000

def tile_strip(text,glyphs):
    if len(text)>4 or any(c not in glyphs for c in text):
        raise ValueError('Header exceeds original four-tile sprite')
    result=bytearray()
    for c in text.ljust(4):
        # Original palette 4 is the dark blue outline (BGR555 4906).
        # Use it as solid ink: white palette 15 vanishes on this light panel.
        bits=[4 if p=='#' else 0 for row in glyphs[c] for p in row] if c!=' ' else [0]*64
        if len(bits)!=64:raise ValueError('Invalid header glyph geometry')
        result.extend(bits[i]|bits[i+1]<<4 for i in range(0,64,2))
    return bytes(result)

def install(legacy,extension,glyphs):
    profile=json.loads((ROOT/'source/skill_header_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/skill_headers.json').read_text(encoding='utf-8'))
    if catalog['policy']!='development_only_needs_review':raise ValueError('Header adoption policy differs')
    for g in profile['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if legacy[off:off+len(raw)]!=raw:raise ValueError('Header source guard differs')
    bank=int(profile['bank'],0);cursor=START;writes=[]
    if extension[START:END]!=b'\xff'*(END-START):raise ValueError('Header allocation overlaps earlier resource')
    rows={r['index']:r for r in catalog['resources']}
    if set(rows)!={45,46,47,48}:raise ValueError('Header resource identity differs')
    for source in profile['resources']:
        idx=source['index'];at=int(source['offset'],0);size=source['stored_span']
        if hashlib.sha256(legacy[at:at+size]).hexdigest()!=source['sha256']:raise ValueError('Original compressed header differs')
        if bank+struct.unpack_from('<I',legacy,bank+4+idx*4)[0]!=at:raise ValueError('Original header bank linkage differs')
        raw=tile_strip(rows[idx]['text'],glyphs)
        # One exactly bounded 128-byte literal run. Keep BIOS RLE type and
        # original decompressed byte count; no unrelated resource relocation.
        packed=struct.pack('<I',(128<<8)|0x30)+b'\x7f'+raw
        extension[cursor:cursor+len(packed)]=packed
        writes.append((bank+4+idx*4,struct.pack('<I',0x1000000+cursor-bank),'skill header graphic '+str(idx)))
        cursor=(cursor+len(packed)+3)&~3
    if cursor>END:raise ValueError('Header allocation exceeds reserved extent')
    return writes,{'resource_count':4,'headers':['특기 설정','특기 사용'],'extension_start':hex(0x1000000+START),'extension_end':hex(0x1000000+cursor),'scope':profile['scope']}
