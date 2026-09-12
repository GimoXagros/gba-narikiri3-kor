"""Verify the complete boot bitmap, protected original credits and ARM loader."""
import argparse,hashlib,json
from pathlib import Path
from splash_credit import install
def main():
    p=argparse.ArgumentParser()
    for n in ('rom','legacy','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();rom=a.rom.read_bytes();old=a.legacy.read_bytes()
    writes,info=install(old);expected=bytearray(old[0xfbb600:0xfce200])
    for at,raw,_ in writes:expected[at-0xfbb600:at-0xfbb600+len(raw)]=raw
    assert rom[0xfbb600:0xfce200]==expected
    assert rom[:4]==old[:4] and rom[0xfce200:0xfce284]==old[0xfce200:0xfce284]
    changed=sum(a!=b for a,b in zip(rom[0xfbb600:0xfce200],old[0xfbb600:0xfce200]))
    assert changed>0
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'changed_bitmap_bytes':changed,**info,'scope':'Exact 240x160 RGB555 bitmap and unchanged ARM DMA/key-wait loader; real boot capture is separate.'}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
