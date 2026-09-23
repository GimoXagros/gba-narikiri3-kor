"""Cold boot, title and full staff traversal through normal core execution."""
import argparse,hashlib,json,struct
from pathlib import Path
from runtime_probe import Probe
from title_staff import ADDED,pixels
from gba_rle import unpack
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    for k in ('rom','core','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    rom=a.rom.read_bytes();report={'rom_sha256':hashlib.sha256(rom).hexdigest()}
    g=Probe(a.core,a.rom,a.out/'normal',None)
    try:
        g.execute({'op':'frames','count':300});g.execute({'op':'screenshot','name':'consent.png'})
        g.execute({'op':'frames','count':1,'buttons':['a']});g.execute({'op':'frames','count':1200})
        g.execute({'op':'screenshot','name':'title.png'})
        raw,_=unpack(rom,0x7b5888+struct.unpack_from('<I',rom,0x7b58a8)[0],len(rom),3584)
        assert g.read_memory(0x06014800,3584)==raw
        g.execute({'op':'frames','count':1,'buttons':['start']});g.execute({'op':'frames','count':100})
        g.execute({'op':'screenshot','name':'title-menu.png'})
    finally:g.lib.retro_unload_game();g.lib.retro_deinit()
    v=bytearray(rom)
    assert v[0x741da4:0x741da8]==bytes.fromhex('699c0008')
    struct.pack_into('<I',v,0x741da4,0x080daff5)
    viewer=a.out/'NARIKIRI3_StaffRoll_Viewer_ONLY.gba';viewer.write_bytes(v)
    report['viewer_sha256']=hashlib.sha256(v).hexdigest()
    table=struct.unpack_from('<I',rom,0xdaeb0)[0]-0x08000000
    ptrs=[]
    while (pointer:=struct.unpack_from('<I',rom,table+len(ptrs)*4)[0]):ptrs.append(pointer)
    texts=[rom[p-0x08000000:rom.index(0,p-0x08000000)].decode('ascii') for p in ptrs]
    assert len(texts)==271 and texts[237:245]==ADDED
    seen=set();screens=[]
    g=Probe(a.core,viewer,a.out/'staff',None)
    try:
        g.execute({'op':'frames','count':300});g.execute({'op':'frames','count':1,'buttons':['a']})
        # All rows are fixed ASCII tiles on a 32-column ring map. Compare live
        # map rows, retaining duplicate-row sequence separately in the ROM check.
        for step in range(300):
            g.execute({'op':'frames','count':32})
            ram=g.read_memory(0x06000000,0x10000)
            for text in texts:
                if not text:continue
                raw=b''.join(struct.pack('<H',0xc000+ord(c)-0x10) for c in text if 0x20<=ord(c)<=0x7e)
                if raw in ram:seen.add(text)
            if step in (230,238,242,246,250,258,268,280):
                screens.append(g.execute({'op':'screenshot','name':f'staff-{step:03d}.png'}))
        assert set(ADDED+['Media JuGGLer','PRODUCED BY','NAMCO']).issubset(seen),set(ADDED)-seen
        assert set(t for t in texts if t).issubset(seen),set(texts)-seen-{''}
    finally:g.lib.retro_unload_game();g.lib.retro_deinit()
    report.update(status='RUNTIME_PASS_VISUAL_PENDING',staff_rows=271,all_unique_staff_lines_seen=len(seen),added_lines=ADDED,screens=screens,
                  scope='Normal input, no RAM interventions, original staff loop directly selected at cold boot. No story-completion or save-compatibility claim.')
    (a.out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='screens'},ensure_ascii=False))
if __name__=='__main__':main()
