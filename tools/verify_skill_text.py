"""Skill text pointer types, metadata, actual getters and description layout."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode,glyph_index
from large_pixel_reference import color_lut,expected_buffer
ROOT=Path(__file__).resolve().parents[1]


def glyphs(raw):
    """Expected original font slots; retain custom Greek-slot kanji as bytes."""
    result=[];i=0
    while i<len(raw):
        c=raw[i]
        if 0x20<=c<=0x7e:
            full={32:'　',46:'。',44:'、'}.get(c,chr(c+0xfee0))
            code=full.encode('cp932');i+=1
        elif 0x81<=c<=0x9f or 0xe0<=c<=0xfc:
            code=raw[i:i+2];i+=2
        else:raise ValueError('Unmodeled large skill byte/control')
        if len(code)!=2:raise ValueError('Truncated large skill glyph')
        result.append(glyph_index(int.from_bytes(code,'big')))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();old=a.legacy.read_bytes();base=0x741ddc
    profile=json.loads((ROOT/'source/skill_text_profile.json').read_text(encoding='utf-8'))
    rows=json.loads((ROOT/'translations/skills.json').read_text(encoding='utf-8'))['records']
    for g in profile['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[off:off+len(raw)]!=raw:raise ValueError('Skill getter/description code changed')
    fields=0;large_repairs=0;desc_repairs=0
    for i,row in enumerate(rows):
        off=base+i*20
        if rom[off+12:off+20]!=old[off+12:off+20]:raise ValueError('Skill cost/attribute metadata changed')
        for delta,key in [(0,'compact'),(4,'large_repair'),(8,'description_repair')]:
            text=row.get(key);ptr=struct.unpack_from('<I',rom,off+delta)[0]-0x08000000
            if text is None:
                if rom[off+delta:off+delta+4]!=old[off+delta:off+delta+4]:raise ValueError('Unselected skill pointer changed')
            else:
                if not 0x100a000<=ptr<0x1020000 or rom[ptr:rom.index(0,ptr)]!=encode(text):raise ValueError('Selected skill text differs')
                fields+=1;large_repairs+=delta==4;desc_repairs+=delta==8
    getters=0;names=0;descriptions=0;positions=0;max_description=0
    for mode in (0,1):
        f=Fixture(rom,mode);u=f.uc;drawn=[]
        def hook(uc,address,size,_):
            if address==0x08001414:drawn.append(tuple(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)))
        handle=u.hook_add(UC_HOOK_CODE,hook)
        def run(pc,stop=0x0203fff0):
            u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
            u.emu_start(pc|1,stop,count=5000000)
            if u.reg_read(UC_ARM_REG_PC)!=stop or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Skill consumer return/stack differs')
        for i in range(390):
            for kind,delta in [(0,0),(1,4)]:
                u.reg_write(UC_ARM_REG_R0,i);u.reg_write(UC_ARM_REG_R1,kind);run(0x08006e3c)
                if u.reg_read(UC_ARM_REG_R0)!=struct.unpack_from('<I',rom,base+i*20+delta)[0]:raise ValueError('Skill name getter differs')
                getters+=1
            for delta in (4,8):
                ptr=struct.unpack_from('<I',rom,base+i*20+delta)[0];at=ptr-0x08000000;raw=rom[at:rom.index(0,at)];codes=glyphs(raw)
                if len(codes)>18:raise ValueError('Skill field exceeds single 18-cell line')
                u.mem_write(0x03000040,bytes([0,0,18,2,0,0,0,13,1,28,15,4,0,0,0,0]))
                u.mem_write(0x0300055c,b'\xa5'*4);u.mem_write(0x03001464,color_lut(mode))
                u.mem_write(0x03000560,expected_buffer(rom,[],mode))
                drawn.clear()
                if delta==4:
                    u.reg_write(UC_ARM_REG_R0,ptr);run(0x08001660);names+=1
                else:
                    # Real getter, formatter, strlen and conditional newline;
                    # stop before the unchanged actor-dependent TP calculation.
                    u.reg_write(UC_ARM_REG_R4,i);run(0x080ca572,0x080ca590);descriptions+=1
                    max_description=max(max_description,len(codes))
                    xy=bytes(u.mem_read(0x03000044,2))
                    # Exactly 18 double-byte cells leave x=18 on row 0;
                    # the next TP glyph wraps. Shorter strings have the
                    # original explicit newline and leave x=0 on row 1.
                    if xy not in (bytes([0,1]),bytes([18,0])):raise ValueError(f'TP continuation position differs: {i} {xy.hex()}')
                want=[(n,0,index) for n,index in enumerate(codes)]
                if drawn!=want:raise ValueError(f'Skill glyph/position differs {i} field {delta}: {drawn!r} != {want!r}')
                if bytes(u.mem_read(0x0300055c,4))!=b'\xa5'*4 or bytes(u.mem_read(0x03001464,4))!=color_lut(mode):raise ValueError('Large font buffer boundary or palette changed')
                if bytes(u.mem_read(0x03000560,0xf00))!=expected_buffer(rom,want,mode):raise ValueError('Large skill pixels differ from original font bits')
                positions+=len(codes)
        u.hook_del(handle)
    r={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'skill_records':390,'selected_text_fields':fields,'large_name_repairs':large_repairs,'description_repairs':desc_repairs,'name_getter_cases':getters,'large_name_cases':names,'actual_description_and_newline_cases':descriptions,'large_glyph_position_cases':positions,'maximum_description_cells':max_description,'metadata_preserved':True,'scope':'All 390 typed records and real name getters; large name and actual description/newline caller in both modes, observed 18-cell line. Stops before actor-dependent TP calculation. Normal skill acquisition, all menus and use remain separate.'}
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))


if __name__=='__main__':main()
