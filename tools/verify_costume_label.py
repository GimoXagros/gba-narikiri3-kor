"""Verify the styled menu atlas, bounded relocation and original CPU loaders."""
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
from gba_rle import unpack


def main():
    p=argparse.ArgumentParser()
    for n in ('rom','legacy','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();rom=a.rom.read_bytes();old=a.legacy.read_bytes()
    profile=json.loads((ROOT/'source/costume_label_profile.json').read_text(encoding='utf-8'))
    extension=bytearray(b'\xff'*0x1000000)
    writes,info=install(old,extension)
    base=int(profile['relocated_atlas'],0);size=profile['new_atlas_bytes']
    oldbase=int(profile['atlas_offset'],0);oldsize=profile['atlas_bytes']
    mt=int(profile['relocated_map'],0);limit=int(profile['extension_limit'],0)
    if rom[base:limit]!=extension[base-0x1000000:limit-0x1000000]:raise ValueError('Relocated payload differs')
    if rom[oldbase:oldbase+oldsize]!=old[oldbase:oldbase+oldsize]:raise ValueError('Original atlas changed')
    for off,raw,_ in writes:
        if rom[off:off+len(raw)]!=raw:raise ValueError('Consumer write differs')
    for g in profile['guards']:
        at=int(g['offset'],0);raw=bytearray.fromhex(g['hex'])
        for off,data,_ in writes:
            for i,v in enumerate(data):
                if at<=off+i<at+len(raw):raw[off+i-at]=v
        if rom[at:at+len(raw)]!=raw:raise ValueError('Undeclared menu code/loader change')
    for m in profile['maps']:
        at=int(m['offset'],0);n=m['encoded_bytes']
        if rom[at:at+n]!=old[at:at+n]:raise ValueError('Original menu map changed')
    bank=int(profile['bank'],0)
    for idx in (109,110):
        at=bank+4+idx*4
        if rom[at:at+4]!=old[at:at+4]:raise ValueError('Palette linkage changed')
    pal=bank+struct.unpack_from('<I',old,bank+4+109*4)[0]
    palend=bank+struct.unpack_from('<I',old,bank+4+110*4)[0]
    if rom[pal:palend]!=old[pal:palend]:raise ValueError('Original palettes changed')
    for tid in range(960):
        if tid not in profile['tiles'] and rom[base+tid*32:base+(tid+1)*32]!=old[oldbase+tid*32:oldbase+(tid+1)*32]:
            raise ValueError('Unrelated atlas tile differs')
    actual_map=unpack(rom,mt,limit,1280)[0]
    original_map=decode_stream(old[int(profile['maps'][6]['offset'],0):])[0]
    changes=[i for i in range(640) if actual_map[i*2:i*2+2]!=original_map[i*2:i*2+2]]
    if changes!=[1,6,33,38]:raise ValueError('Map changes outside four blank edge cells')
    if size>=0x8000 or max(profile['styled_tiles'])>=1024:raise ValueError('VRAM map overlaps atlas')
    # Independently sample the three reused menu letters via original maps.
    def pixel(data,atlas_base,tile,x,y):
        v=data[atlas_base+tile*32+(y%8)*4+(x%8)//2]
        return (v>>4) if x%2 else v&15
    for ci,ch in enumerate('갈아입기'):
        if ch not in profile['style_sources']:continue
        src=profile['style_sources'][ch];m=profile['maps'][src['map']-1]
        source_map=decode_stream(old[int(m['offset'],0):])[0]
        for y in range(12):
            for x in range(12):
                sx=src['x']+x;sy=src['y']+y
                tid=struct.unpack_from('<H',source_map,((sy//8)*32+sx//8)*2)[0]&1023
                want=pixel(old,oldbase,tid,sx,sy)
                ox=ci*12+x;oy=y+2
                if want not in (1,2,13,14):want=pixel(old,oldbase,profile['background_tiles'][oy//8],ox,oy)
                dest=profile['styled_tiles'][(oy//8)*6+ox//8]
                if pixel(rom,base,dest,ox,oy)!=want:raise ValueError('Reused original letter differs')
    atlas=Fixture(rom,0);u=atlas.uc
    u.reg_write(UC_ARM_REG_R4,0x08000000+bank)
    u.reg_write(UC_ARM_REG_SP,0x03007e00)
    u.emu_start(0x080c8c61,0x080c8c74,count=10000)
    dma=struct.unpack('<IIII',u.mem_read(0x03002820,16))
    if dma!=(0x08000000+base,0x06000000,0x84001e20,30848):raise ValueError(f'Atlas loader differs: {dma}')
    f=Fixture(rom,0);u=f.uc;scratch=0x02018000
    u.mem_write(0x02003380,struct.pack('<I',scratch));u.mem_write(scratch-4,b'\xa5'*1288)
    decoded=[]
    def intr(uc,number,_):
        pc=uc.reg_read(UC_ARM_REG_PC)
        if bytes(uc.mem_read(pc-2,2))!=b'\x14\xdf':raise ValueError('Unexpected BIOS call')
        src=uc.reg_read(UC_ARM_REG_R0);dest=uc.reg_read(UC_ARM_REG_R1)
        raw=bytes(uc.mem_read(src,2048))
        data,used=unpack(raw,0,len(raw),1280)
        if len(data)!=1280 or dest!=scratch:raise ValueError('Map decompression extent differs')
        uc.mem_write(dest,data);decoded.append((src,data))
    u.hook_add(UC_HOOK_INTR,intr)
    for reg,val in [(UC_ARM_REG_R0,7),(UC_ARM_REG_R1,1),(UC_ARM_REG_R2,0),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,val)
    u.emu_start(0x080c8e21,0x0203fff0,count=10000)
    if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or len(decoded)!=1:raise ValueError('Map loader did not return')
    if bytes(u.mem_read(scratch-4,4))!=b'\xa5'*4 or bytes(u.mem_read(scratch+1280,4))!=b'\xa5'*4:raise ValueError('Map scratch boundary changed')
    dma=struct.unpack('<IIII',u.mem_read(0x03002820,16))
    if dma!=(scratch,0x06008000,0x84000140,1280):raise ValueError(f'Map DMA differs: {dma}')
    if decoded[0]!=(0x08000000+mt,actual_map):raise ValueError('Relocated map loader differs')
    if u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Map loader stack differs')
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),**info,
            'copied_letter_pixel_checks':432,'unchanged_original_menu_maps':34,'atlas_dma_bytes':30848,'changed_map_cells':changes,
            'original_map_dma_bytes':1280,'scope':'Original bank lookup, decompression dispatch and DMA queue execute. BIOS RLE output modeled with strict bounds. Original atlas and compressed maps preserved; copied atlas changes limited to twelve declared tiles, four map edge cells and atlas DMA length. Normal controller behavior requires separate runtime review.'}
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
