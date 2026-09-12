"""Add an explicitly authored pixel credit to the inherited Mode 3 bitmap."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def install(legacy):
    p=json.loads((ROOT/'source/splash_credit.json').read_text(encoding='utf8'))
    base=int(p['bitmap_offset'],0)
    if hashlib.sha256(legacy[base:base+240*160*2]).hexdigest()!=p['bitmap_sha256']:raise ValueError('Splash source bitmap differs')
    if hashlib.sha256(legacy[0xfce200:0xfce284]).hexdigest()!=p['boot_sha256']:raise ValueError('Splash DMA/input code differs')
    if p['text']!='Xagros':raise ValueError('Unapproved credit')
    width=(len(p['text'])-1)*p['advance']+5
    if p['x']+width>240 or p['y']+7>160:raise ValueError('Credit outside display')
    writes=[]
    for y in range(7):
        offset=base+((p['y']+y)*240+p['x'])*2
        row=bytearray(width*2)
        if legacy[offset:offset+len(row)]!=bytes(len(row)):raise ValueError('Credit overlaps existing artwork')
        for n,ch in enumerate(p['text']):
            glyph=p['glyphs'][ch]
            if len(glyph)!=7 or any(len(r)!=5 or set(r)-{'.','#'} for r in glyph):raise ValueError('Invalid authored glyph')
            for x,pixel in enumerate(glyph[y]):
                if pixel=='#':struct.pack_into('<H',row,(n*p['advance']+x)*2,0x7fff)
        writes.append((offset,bytes(row),'splash-credit-Xagros'))
    return writes,{'text':p['text'],'rectangle':[p['x'],p['y'],width,7],'original_credits_preserved':True,'boot_code_unchanged':True}
