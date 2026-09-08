"""Find aligned Thumb BL targets; candidate code references require context review."""
import argparse,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--target',type=lambda x:int(x,0),required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
rom=a.rom.read_bytes();md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);out=[]
for off in range(0,0xddcc0,2):
    hi,lo=struct.unpack_from('<HH',rom,off)
    if hi&0xf800!=0xf000 or lo&0xf800!=0xf800:continue
    delta=((hi&0x7ff)<<12)|((lo&0x7ff)<<1)
    if delta&0x400000:delta-=0x800000
    if 0x08000000+off+4+delta==a.target:
        out.append(f'\nCALL {off+0x08000000:08X}')
        out.extend(f'{i.address:08X}: {i.bytes.hex():10} {i.mnemonic} {i.op_str}' for i in md.disasm(rom[off-48:off+48],0x08000000+off-48))
a.out.write_text('\n'.join(out),encoding='utf-8');print('\n'.join(x for x in out if x.startswith('\nCALL')))
