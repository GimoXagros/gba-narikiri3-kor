"""Losslessly unpack the two-color consent bitmap through the native BIOS."""
import struct
from gba_rle import unpack
from v13a_changes import assemble,sha

def boot_writes(base,tc,out):
    raw,end=unpack(base,0xfbb600,0xfbd354,76800)
    if sha(raw)!='82773ec065898089374f4e7834a1d8e83adb8e5be8f5ebbc91dd0bd742e52a75':raise ValueError('Boot bitmap identity')
    pixels=struct.unpack('<38400H',raw)
    if set(pixels)!={0,0x7fff}:raise ValueError('Unsupported bitmap color')
    packed=bytes(sum((pixels[i+j]!=0)<<j for j in range(8)) for i in range(0,len(pixels),8))
    decoded=b''.join(struct.pack('<H',0x7fff if byte>>bit&1 else 0) for byte in packed for bit in range(8))
    if len(packed)!=4800 or decoded!=raw:raise ValueError('Boot bitplane roundtrip')
    section,_=assemble(tc,out,['boot_bitunpack.s'],0x08fbcd2c,'boot_bitunpack')
    code=section('text')
    if len(code)!=64 or sha(code)!='0fb6d057316c1fc27c225e174af0a2e5fae18d1c4fccb3240d6503d1fa1a369c':raise ValueError('Reviewed boot stub identity')
    delta=0x08fbcd2c-(0x08fce214+8)
    branch=struct.pack('<I',0xea000000|((delta>>2)&0xffffff))
    return [dict(label='consent bitplane first span',at=0xfbb600,data=packed[:2416],end=0xfbbf70),
            dict(label='consent bitplane second span',at=0xfbc3dc,data=packed[2416:],end=0xfbcd2c),
            dict(label='native BIOS consent decoder',at=0xfbcd2c,data=code,end=0xfbcd6c),
            dict(label='native BIOS consent hook',at=0xfce214,data=branch,end=0xfce218)]
