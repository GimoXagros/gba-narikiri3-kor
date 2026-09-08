"""Verify exact relocated names and agreement of both emitted small consumers."""
import argparse,hashlib,json,struct
from pathlib import Path
from text_codec import encode
from verify_small_consumer import Fixture
from verify_simple_consumer import SimpleFixture
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rom=a.rom.read_bytes()
    selections=[]
    speakers=json.loads((ROOT/'translations/speakers.json').read_text(encoding='utf-8'))
    for i,t in enumerate(speakers['names']):
        if t is not None:selections.append((f'speaker-{i:03d}',0xec7944+i*20+4,t))
    for file,base,stride,field in [('skills.json',0x741ddc,20,0),('actors.json',0x1000e4,72,4)]:
        for i,r in enumerate(json.loads((ROOT/'translations'/file).read_text(encoding='utf-8'))['records']):selections.append((r['id'],base+i*stride+field,r['compact']))
    lex=json.loads((ROOT/'translations/items-monsters.json').read_text(encoding='utf-8'))['groups']
    for group,base,stride in [('item',0x105758,24),('monster',0x1021ac,56)]:
        for i,r in enumerate(lex[group]):selections.append((r['id'],base+i*stride,r['compact']))
    if len(selections)!=910:raise ValueError('Expected selected table population differs')
    values=[]
    for identity,offset,t in selections:
        ptr=struct.unpack_from('<I',rom,offset)[0]-0x08000000
        if not 0x1009000<=ptr<0x1060000:raise ValueError('Relocated pointer outside named text allocations')
        raw=rom[ptr:rom.index(0,ptr)]
        if raw!=encode(t):raise ValueError(f'Relocated value mismatch {identity}')
        values.append((identity,raw))
    for mode in (0,1):
        main=Fixture(rom,mode);simple=SimpleFixture(rom,mode)
        for identity,raw in values:
            main.draw(raw);simple.draw_simple(raw)
            if main.pixels()!=simple.pixels():raise ValueError(f'Consumer disagreement {identity} mode {mode}')
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'pointer_value_cases':len(values),'both_renderer_mode_cases':len(values)*2,'scope':'Selected static table records and isolated renderers; excludes unresolved duplicate tables, player save branches and whole-game reachability/layout'}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
