"""Run original music-title centering/rendering and field-speaker branches."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode,glyph_index
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();old=a.legacy.read_bytes();profile=json.loads((ROOT/'source/notice_text_profile.json').read_text(encoding='utf-8'));rows=json.loads((ROOT/'translations/notices.json').read_text(encoding='utf-8'))['records']
    for g in profile['guards']:
        off=int(g['offset'],0)
        for i,v in enumerate(bytes.fromhex(g['hex'])):
            if not 0xa5620<=off+i<0xa5624 and rom[off+i]!=v:raise ValueError('Notice original consumer changed')
    for i in range(12):
        off=0xd441bc+16*i
        if rom[off:off+12]!=old[off:off+12]:raise ValueError('Music score pointer, BGM ID, or timing changed')
    for i,row in enumerate(rows):
        ptr=struct.unpack_from('<I',rom,int(row['pointer_offset'],0))[0]-0x08000000
        raw=encode(row['text'].replace(' ','　') if i<12 else row['text'])
        if not 0x1100000<=ptr<0x1101000 or rom[ptr:rom.index(0,ptr)]!=raw:raise ValueError('Notice relocated bytes differ')
    titles=0;glyphs=0;field=0;getters=0;maximum=0;bios_fills=[]
    for mode in (0,1):
        f=Fixture(rom,mode);expected=Fixture(rom,mode);u=f.uc
        if rom[0xdd428:0xdd42c]!=bytes.fromhex('0bdf7047'):raise ValueError('CpuSet wrapper changed')
        def cpu_set(uc,addr,size,_):
            source,dest,control=(uc.reg_read(reg) for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2))
            if control!=0x050003c0 or dest!=0x03000560:raise ValueError('Unmodeled BIOS transfer')
            uc.mem_write(dest,bytes(uc.mem_read(source,4))*0x3c0)
            bios_fills.append((dest,0xf00));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,cpu_set,begin=0x080dd428,end=0x080dd428)
        def run(pc,r0=0,r1=0,end=0x0203fff0):
            for reg,val in [(UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,val)
            u.emu_start(pc|1,end,count=5000000)
            if u.reg_read(UC_ARM_REG_PC)!=end or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Notice return/stack mismatch')
        drawn=[]
        def observe(uc,addr,size,_):
            drawn.append(tuple(uc.reg_read(reg) for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)))
        handle=u.hook_add(UC_HOOK_CODE,observe,begin=0x08001414,end=0x08001414)
        for row in rows[:12]:
            i=row['index'];text=row['text'].replace(' ','　');ptr=struct.unpack_from('<I',rom,0xd441c8+16*i)[0]
            u.mem_write(0x02002040,struct.pack('<h',i));u.reg_write(UC_ARM_REG_R5,0x02002000)
            run(0x0809d7c6,end=0x0809d7de)
            if (u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1),u.reg_read(UC_ARM_REG_R2),u.reg_read(UC_ARM_REG_R3))!=(ptr,0,120,0):raise ValueError('Actual music ID/title lookup differs')
            centered='　'*((19-len(text))//2)+text;raw=encode(centered)+b'\0'
            if len(raw)>44:raise ValueError('Music title exceeds original +04..+2F object buffer')
            for variant in (0,1):
                obj=bytearray(b'\xa5'*64);struct.pack_into('<h',obj,2,variant);u.mem_write(0x02002000,bytes(obj))
                run(0x080167b0,0x02002000,ptr)
                want=bytes(obj[:4])+raw+bytes(obj[4+len(raw):])
                if bytes(u.mem_read(0x02002000,64))!=want:raise ValueError('Actual music centering/copy extent differs')
                # Real presentation initializer and renderer. Per-character
                # delay starts at zero in this CPU fixture; original palette
                # selection, line geometry, font drawing and spacing execute.
                u.mem_write(0x03000040,bytes([0,0,18,2,0,0,0,13,1,28,15,4,0,0,0,0]))
                drawn.clear();run(0x08016780,0x02002000)
                codes=[]
                for ch in centered:
                    full=chr(ord(ch)+0xfee0) if '!'<=ch<='~' else ch
                    b=encode(full)
                    if len(b)!=2:raise ValueError('Unmodeled music glyph')
                    codes.append(glyph_index(int.from_bytes(b,'big')))
                # 0EC4 sets the physical map anchor separately (+08/+0A)
                # and resets the font-buffer cursor to relative (0,0).
                context=bytes(u.mem_read(0x03000040,16))
                if (context[8],context[10])!=(1,1 if variant==0 else 17):raise ValueError('Music map anchor changed')
                want=[(n,0,slot) for n,slot in enumerate(codes)]
                if drawn!=want:raise ValueError(f'Music title {i} glyph positions differ: {drawn!r} != {want!r}')
                titles+=1;glyphs+=len(codes);maximum=max(maximum,len(raw))
        u.hook_del(handle)
        name=rows[-1]['text'];target=struct.unpack_from('<I',rom,0xa5620)[0]
        for ident,at in ((56,0xa5620),(57,0xa5620),(73,0xa5618),(74,0xa5618),(-1,0xa5628)):
            run(0x080a55f4,ident&0xffffffff)
            if u.reg_read(UC_ARM_REG_R0)!=struct.unpack_from('<I',rom,at)[0]:raise ValueError('Field special-name branch differs')
            getters+=1
        for ids in ((56,),(57,),(56,57),(57,56)):
            f.draw(b'');u.mem_write(0x02000000,bytes([21,3,29,7,21,3,0,13]))
            u.reg_write(UC_ARM_REG_R5,len(ids));u.reg_write(UC_ARM_REG_R6,0x02000000)
            u.mem_write(0x03007e04,struct.pack('<II',ids[0],ids[-1]))
            run(0x080a5692,end=0x080a56ca)
            for line in range(len(ids)):
                expected.draw(encode(name),clear=line==0,x=21,y=3+line)
            if f.pixels()!=expected.pixels():
                differing=[(x,y) for y in range(32) for x in range(32) if f.tile(x,y)!=expected.tile(x,y)]
                raise ValueError(f'Actual field formatter differs: mode={mode}, ids={ids}, window={bytes(u.mem_read(0x02000000,8)).hex()}, scratch={bytes(u.mem_read(0x03001468,32)).hex()}, tiles={differing[:30]}')
            field+=1
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'selected_fields':13,'music_title_center_copy_and_render_cases':titles,'music_glyph_positions':glyphs,'maximum_centered_title_bytes_including_nul':maximum,'music_buffer_bytes':44,'special_getter_cases':getters,'field_formatter_cases':field,'bios_font_buffer_fill_substitutions':len(bios_fills),'music_and_action_metadata_preserved':True,'scope':'Original music table lookup, centering, bounded object copy and actual large renderer, both positions/modes; only BIOS CpuSet fixed 3840-byte word-fill is modeled. Original field-name special branches and one/two-row small formatter. Normal music-event and special-character progression remain separate.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
