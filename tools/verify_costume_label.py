"""Verify only eight menu-label tiles change, plus original atlas/map loading."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from verify_graphics_candidate_edges import decode_stream
from costume_label import install, ROOT


def main():
    p=argparse.ArgumentParser()
    for n in ('rom','legacy','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();rom=a.rom.read_bytes();old=a.legacy.read_bytes()
    profile=json.loads((ROOT/'source/costume_label_profile.json').read_text(encoding='utf-8'))
    glyphs=json.loads((ROOT/'fonts/dalmoori-wansung.json').read_text(encoding='utf-8'))
    writes,info=install(old,glyphs);base=int(profile['atlas_offset'],0);size=profile['atlas_bytes']
    expected=bytearray(old[base:base+size])
    for off,raw,_ in writes:expected[off-base:off-base+len(raw)]=raw
    if rom[base:base+size]!=expected:raise ValueError('Atlas pixels outside selected label changed')
    for g in profile['guards']:
        at=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[at:at+len(raw)]!=raw:raise ValueError('Menu code/loader changed')
    for m in profile['maps']:
        at=int(m['offset'],0);n=m['encoded_bytes']
        if rom[at:at+n]!=old[at:at+n]:raise ValueError('Original menu map changed')
    bank=int(profile['bank'],0)
    for idx in (0,7,109,110):
        at=bank+4+idx*4
        if rom[at:at+4]!=old[at:at+4]:raise ValueError('Atlas/map/palette linkage changed')
    pal=bank+struct.unpack_from('<I',old,bank+4+109*4)[0]
    palend=bank+struct.unpack_from('<I',old,bank+4+110*4)[0]
    if rom[pal:palend]!=old[pal:palend]:raise ValueError('Original palettes changed')
    # Independently decode each written tile into a complete 32x16 bitmap.
    for y in range(16):
        for x in range(32):
            tid=profile['tiles'][(y//8)*4+x//8]
            b=rom[base+tid*32+(y%8)*4+(x%8)//2]
            got=(b>>4) if x%2 else b&15
            bg=profile['background_tiles'][y//8]
            b=old[base+bg*32+(y%8)*4+(x%8)//2]
            want=(b>>4) if x%2 else b&15
            if 4<=y<12 and glyphs['갈아입기'[x//8]][y-4][x%8]=='#':want=14
            if got!=want:raise ValueError('Glyph/background pixel differs')
    atlas=Fixture(rom,0);u=atlas.uc
    u.reg_write(UC_ARM_REG_R4,0x08000000+bank)
    u.reg_write(UC_ARM_REG_SP,0x03007e00)
    u.emu_start(0x080c8c61,0x080c8c74,count=10000)
    dma=struct.unpack('<IIII',u.mem_read(0x03002820,16))
    if dma!=(0x08000000+base,0x06000000,0x84001e00,30720):raise ValueError(f'Atlas loader differs: {dma}')
    f=Fixture(rom,0);u=f.uc;scratch=0x02018000
    u.mem_write(0x02003380,struct.pack('<I',scratch));u.mem_write(scratch-4,b'\xa5'*1288)
    decoded=[]
    def intr(uc,number,_):
        pc=uc.reg_read(UC_ARM_REG_PC)
        if bytes(uc.mem_read(pc-2,2))!=b'\x11\xdf':raise ValueError('Unexpected BIOS call')
        src=uc.reg_read(UC_ARM_REG_R0);dest=uc.reg_read(UC_ARM_REG_R1)
        data,used,_=decode_stream(bytes(uc.mem_read(src,2048)))
        if len(data)!=1280 or dest!=scratch:raise ValueError('Map decompression extent differs')
        uc.mem_write(dest,data);decoded.append((src,data))
    u.hook_add(UC_HOOK_INTR,intr)
    for reg,val in [(UC_ARM_REG_R0,7),(UC_ARM_REG_R1,1),(UC_ARM_REG_R2,0),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,val)
    u.emu_start(0x080c8e21,0x0203fff0,count=10000)
    if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or len(decoded)!=1:raise ValueError('Map loader did not return')
    if bytes(u.mem_read(scratch-4,4))!=b'\xa5'*4 or bytes(u.mem_read(scratch+1280,4))!=b'\xa5'*4:raise ValueError('Map scratch boundary changed')
    dma=struct.unpack('<IIII',u.mem_read(0x03002820,16))
    if dma!=(scratch,0x06008000,0x84000140,1280):raise ValueError(f'Map DMA differs: {dma}')
    expected_map=decode_stream(old[int(profile['maps'][6]['offset'],0):])[0]
    if decoded[0][1]!=expected_map:raise ValueError('Original map changed in loader')
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),**info,
            'pixel_checks':512,'unchanged_menu_maps':34,'original_atlas_dma_bytes':30720,
            'original_map_dma_bytes':1280,'scope':'Original bank lookup and DMA queue execute; BIOS LZ77 output is modeled with bounds. Whole atlas and 34 maps, palettes and consumers are preserved except eight declared tiles. Normal controller selection/change and all runtime states need separate review.'}
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
