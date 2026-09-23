"""Verify original credits, insertion order and protected bitmap bytes."""
import argparse,json,struct,hashlib
from pathlib import Path
from title_staff import ADDED,START,END,install,pixels
from gba_rle import unpack

def main():
    p=argparse.ArgumentParser()
    for k in ('rom','legacy','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();rom=a.rom.read_bytes();old=a.legacy.read_bytes()
    ext=bytearray(b'\xff'*0x1000000);writes,info=install(old,ext)
    for at,data,_ in writes:assert rom[at:at+len(data)]==data
    assert rom[0x1000000+START:0x1000000+END]==ext[START:END]
    oldrows=list(struct.unpack_from('<262I',old,0xfa4ea4))
    at=struct.unpack_from('<I',rom,0xdaeb0)[0]-0x08000000
    newrows=list(struct.unpack_from('<272I',rom,at))
    assert newrows[:235]+newrows[245:]==oldrows
    assert newrows[235:237]==[0x081c3d80]*2
    for pointer,text in zip(newrows[237:245],ADDED):
        start=pointer-0x08000000;assert rom[start:rom.index(0,start)].decode('ascii')==text
    source,_=unpack(old,0x7b7ca8,len(old),3584)
    target,_=unpack(rom,0x1184000,len(rom),3584)
    assert pixels(source)[18:]==pixels(target)[18:]
    assert rom[0xfbb600:0xfbb600+100*480]==old[0xfbb600:0xfbb600+100*480]
    assert rom[0xfbb600+100*480:0xfce200]==bytes(60*480)
    assert rom[0xfce200:0xfce284]==old[0xfce200:0xfce284]
    assert rom[0x741d94:0x741dc4]==old[0x741d94:0x741dc4]
    info.update(status='PASS',rom_sha256=hashlib.sha256(rom).hexdigest(),
                normal_game_dispatch_preserved=True,consent_prompt_and_loader_preserved=True)
    a.out.write_text(json.dumps(info,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(info,ensure_ascii=False))
if __name__=='__main__':main()
