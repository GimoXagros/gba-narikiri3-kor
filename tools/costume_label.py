"""Style the clothing-change label using the existing embossed menu artwork."""
import hashlib
import json
from pathlib import Path
import struct
from verify_graphics_candidate_edges import decode_stream
from gba_rle import pack_literals

ROOT = Path(__file__).resolve().parents[1]


def install(legacy, extension):
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
    decoded_maps = {}
    for m in p['maps']:
        at=int(m['offset'],0)
        decoded_maps[m['index']]=decode_stream(legacy[at:at+m['encoded_bytes']])[0]
    def source_pixel(map_id,x,y):
        entries=decoded_maps[map_id]
        e=struct.unpack_from('<H',entries,((y//8)*32+x//8)*2)[0]
        if e&0xc00:raise ValueError('Unexpected flipped source glyph')
        b=legacy[base+(e&1023)*32+(y%8)*4+(x%8)//2]
        return (b>>4) if x%2 else b&15
    pixels=[]
    for y in range(16):
        row=[]
        for x in range(48):
            tile=p['background_tiles'][y//8]
            b=legacy[base+tile*32+(y%8)*4+(x%8)//2]
            row.append((b>>4) if x%2 else b&15)
        pixels.append(row)
    for ci,ch in enumerate(p['korean_label']):
        if ch in p['style_sources']:
            src=p['style_sources'][ch]
            for y in range(12):
                for x in range(12):
                    c=source_pixel(src['map'],src['x']+x,src['y']+y)
                    if c in (1,2,13,14):pixels[2+y][ci*12+x]=c
        else:
            mask=p['authored_gal_mask']
            if ch!='갈' or len(mask)!=12 or any(len(r)!=12 or set(r)-{'.','#'} for r in mask):
                raise ValueError('Unverified authored letter')
            points={(x,y) for y,row in enumerate(mask) for x,v in enumerate(row) if v=='#'}
            outline={(x+dx,y+dy) for x,y in points for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))}-points
            for x,y in outline:
                if not (0<=x<12 and 0<=y<12):raise ValueError('Outline clips letter cell')
                pixels[y+2][ci*12+x]=14
            for x,y in points:pixels[y+2][ci*12+x]=13
    atlas=bytearray(legacy[base:base+p['atlas_bytes']])+bytearray(128)
    if len(atlas)!=p['new_atlas_bytes']:raise ValueError('Atlas extension size differs')
    for i,tid in enumerate(p['styled_tiles']):
        raw=bytearray()
        for y in range(8):
            for x in range(0,8,2):
                row=pixels[(i//6)*8+y]
                raw.append(row[(i%6)*8+x]|row[(i%6)*8+x+1]<<4)
        atlas[tid*32:(tid+1)*32]=raw
    tilemap=bytearray(decoded_maps[7])
    for i,tid in enumerate(p['styled_tiles']):
        struct.pack_into('<H',tilemap,((i//6)*32+1+i%6)*2,tid)
    packed=pack_literals(tilemap)
    at=int(p['relocated_atlas'],0);mt=int(p['relocated_map'],0);limit=int(p['extension_limit'],0)
    if mt!=at+len(atlas) or mt+len(packed)>limit:raise ValueError('Resource overlap/extent')
    if extension[at-0x1000000:limit-0x1000000]!=b'\xff'*(limit-at):raise ValueError('Resource allocation occupied')
    extension[at-0x1000000:mt-0x1000000]=atlas
    extension[mt-0x1000000:mt-0x1000000+len(packed)]=packed
    if legacy[0xc8c6c:0xc8c70]!=bytes.fromhex('f022d201'):raise ValueError('Original atlas DMA length instruction differs')
    writes=[(bank+4,struct.pack('<I',at-bank),'costume atlas relative offset'),
            (bank+4+7*4,struct.pack('<I',mt-bank),'costume map relative offset'),
            (0xc8c6c,bytes.fromhex('f122'),'costume atlas DMA: 241 << 7 bytes')]
    return writes,{'text':p['korean_label'],'japanese':'きがえ','rectangle':[8,0,48,16],
                  'original_style_letters':3,'authored_style_letters':1,'atlas_bytes':len(atlas),
                  'additional_vram_tiles':4,'atlas_end_vram':'0x06007880','next_map_vram':'0x06008000',
                  'palette_preserved':True,'atlas_offset':hex(at),'map_offset':hex(mt)}
