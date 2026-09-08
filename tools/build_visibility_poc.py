"""Non-distributable, temporary three-glyph visibility experiment.

Builds from verified Japanese + legacy IPS. Every new change is planned
against immutable K1.1; composition with legacy patch is explicit.
"""
import argparse,hashlib,json
from pathlib import Path
from survey_rom import ips_records

J='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394'
K='8440f3e3db46c474c81cf84098798f07ab91aa13d48431c523c309a0af363010'
IPS='207e69c0617997ff410ee769030e9ea4e1dcc7f6500dde93e7154cd9a859179a'
def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--ips',type=Path,required=True);p.add_argument('--glyphs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    j=a.j.read_bytes();patch=a.ips.read_bytes()
    if sha(j)!=J or sha(patch)!=IPS:raise ValueError('Unsupported input')
    legacy=bytearray(j);records,trunc=ips_records(patch)
    if trunc is not None:raise ValueError('Unexpected legacy truncation')
    for offset,data in records:legacy[offset:offset+len(data)]=data
    legacy=bytes(legacy)
    if sha(legacy)!=K:raise ValueError('Legacy reconstruction mismatch')
    glyphs=json.loads(a.glyphs.read_text(encoding='utf-8'))
    writes=[]
    def plan(offset,data,reason):
        writes.append(dict(offset=offset,expected=legacy[offset:offset+len(data)].hex(),final=data.hex(),reason=reason))
    for base in (0xfbcc4,0xfdcc4):
        # Space determines background; lowercase-a determines ink in this atlas.
        space=legacy[base+0x10*32:base+0x11*32]
        if len(set(space))!=1:raise ValueError('Space tile is not uniform')
        bg=space[0]&15
        tile=legacy[base+0x51*32:base+0x52*32]
        fg=set(n for b in tile for n in (b&15,b>>4))-{bg}
        if len(fg)!=1:raise ValueError('Unresolved palette roles')
        ink=fg.pop()
        for raw,c in zip(b'abc','브라운'):
            rows=glyphs[c]
            if len(rows)!=8 or any(len(r)!=8 or set(r)-{'.','#'} for r in rows):raise ValueError('Invalid 8x8 glyph')
            pixels=[ink if bit=='#' else bg for row in rows for bit in row]
            data=bytes(pixels[i]|pixels[i+1]<<4 for i in range(0,64,2))
            # Independent unpack validates final packing over every pixel.
            if [n for b in data for n in (b&15,b>>4)]!=pixels:raise ValueError('Tile round trip')
            plan(base+(raw-0x10)*32,data,f'TEMPORARY ASCII {chr(raw)} -> Dalmoori {c}')
    if legacy[0x1bde70:0x1bde78]!=bytes.fromhex('ccded7b3dd000000'):raise ValueError('Speaker slot changed')
    plan(0x1bde70,b'abc\0\0\0\0\0','POC Brown compact name; 8-byte slot')
    ranges=sorted((w['offset'],w['offset']+len(bytes.fromhex(w['final']))) for w in writes)
    if any(b>c for (_,b),(c,_) in zip(ranges,ranges[1:])):raise ValueError('Overlapping writers')
    out=bytearray(legacy)
    for w in writes:
        start=w['offset'];data=bytes.fromhex(w['final']);out[start:start+len(data)]=data
    explained={i for s,e in ranges for i in range(s,e)}
    if any(x!=y and i not in explained for i,(x,y) in enumerate(zip(legacy,out))):raise ValueError('Unexplained final diff')
    if out[0xddcc4:0xfbcc4]!=legacy[0xddcc4:0xfbcc4]:raise ValueError('Large font changed')
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'nd3-small-visibility-ONLY.gba').write_bytes(out)
    report=dict(status='EXPERIMENT_ONLY_NOT_RELEASE',j_sha256=J,legacy_sha256=K,target_sha256=sha(out),writes=writes,
                claim='Three-glyph visibility only. ASCII collisions intentionally unresolved outside the experiment.')
    (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='writes'},ensure_ascii=False))
if __name__=='__main__':main()
