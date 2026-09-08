"""Execute original caption placement; resolve original sprite frame descriptors."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();old=a.legacy.read_bytes()
    profile=json.loads((ROOT/'source/battle_caption_profile.json').read_text(encoding='utf-8'))
    texts={r['id']:r['text'] for r in json.loads((ROOT/'translations/battle_captions.json').read_text(encoding='utf-8'))['records']}
    glyphs=json.loads((ROOT/'fonts/dalmoori-wansung.json').read_text(encoding='utf-8'))
    f=Fixture(rom,0);u=f.uc
    def run(pc,r0,r1=0):
        for reg,v in [(UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,v)
        u.emu_start(pc|1,0x0203fff0,count=100000)
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Caption CPU return/stack differs')
    bank=int(profile['bank'],0);gfx=int(profile['graphics_offset'],0)
    run(0x08003444,0x08000000+bank,profile['graphics_index'])
    if u.reg_read(UC_ARM_REG_R0)!=0x08000000+gfx:raise ValueError('Original bank getter does not select the adopted graphics')
    # Protect all bank content except the exact 12-letter pool, and every
    # icon/hand/background frame, palette, allocation count and action code.
    pool=int(profile['tile_pool_offset'],0);end=pool+profile['tile_pool_count']*32
    if rom[gfx:pool]!=old[gfx:pool] or rom[end:0xd38cfc]!=old[end:0xd38cfc]:raise ValueError('Non-caption graphics/palette changed')
    for guard in profile['guards']:
        start=int(guard['offset'],0);raw=bytes.fromhex(guard['hex'])
        if rom[start:start+len(raw)]!=raw:raise ValueError('Original caption code/non-text structure changed')
    count=0
    for row in profile['records']:
        context=0x02008000;objects=0x02009000;text=texts[row['id']]
        u.mem_write(context,bytes(0x80));u.mem_write(context+0xa,struct.pack('<h',row['index']))
        for i in range(13):
            addr=objects+i*0x40
            u.mem_write(context+0x14+i*4,struct.pack('<I',addr));u.mem_write(addr,bytes(0x40))
        run(int(profile['layout_consumer'],0),context)
        visible=[]
        for i in range(8):
            obj=bytes(u.mem_read(objects+(5+i)*0x40,0x40))
            if struct.unpack_from('<H',obj,0x18)[0]&0x80:continue
            x,y=struct.unpack_from('<hh',obj,0xc);frame=struct.unpack_from('<H',obj,0x12)[0]
            ptr=struct.unpack_from('<I',rom,int(profile['frame_table'],0)+4+frame*4)[0]-0x08000000
            n=struct.unpack_from('<I',rom,ptr)[0]
            if n!=1:raise ValueError('Caption frame is not one original sprite component')
            dx,dy,shape,palette,tile=struct.unpack_from('<bbBBI',rom,ptr+4)
            if frame==5:
                if (dx,dy,shape,palette,tile)!=(0,0,1,2,40):raise ValueError('Caption background sprite changed')
                continue
            if (dx,dy,shape,palette)!=(0,0,0,2):raise ValueError('Caption letter is not original 8x8 palette-2 sprite')
            raw=rom[gfx+tile*32:gfx+(tile+1)*32]
            pixels=[v for b in raw for v in (b&15,b>>4)]
            visible.append((x,y,pixels))
        anchor=rom[0x7c1d35+row['index']]-12
        start=anchor+(24-8*len(text))//2
        if len(visible)!=len(text):raise ValueError('Wrong number of visible caption letters')
        for i,((x,y,pixels),char) in enumerate(zip(visible,text)):
            want=[15 if v=='#' else 0 for line in glyphs[char] for v in line]
            if (x,y)!=(start+i*8,57) or pixels!=want:raise ValueError('Original placement/frame lookup does not display the selected Korean caption')
            count+=1
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'caption_count':4,'letter_pixel_cases':count,'original_layout_cpu_cases':4,'nontext_icons_palette_frames_and_action_code_preserved':True,'scope':'Original graphics bank getter, eight-component caption placement and sprite frame descriptors. Exact Korean pixels, positions and untouched icon/palette/code checked; full GPU and input behavior require normal runtime verification.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
