"""Run the real variadic formatter and patched renderer for adopted UI strings."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from text_codec import encode
from verify_small_consumer import Fixture

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();profile=json.loads((ROOT/'source/ui_profile.json').read_text(encoding='utf-8'))['records']
    translations={r['id']:r['text'] for r in json.loads((ROOT/'translations/ui.json').read_text(encoding='utf-8'))['records']}
    count=0
    for mode in (0,1):
        f=Fixture(rom,mode);expected=Fixture(rom,mode);u=f.uc
        for row in profile:
            identity=row['id'];text=translations[identity];ptr=struct.unpack_from('<I',rom,int(row['pointer_offset'],16))[0]
            off=ptr-0x08000000
            if not 0x1060000<=off<0x1070000 or rom[off:rom.index(0,off)]!=encode(text):raise ValueError('Relocated UI bytes differ')
            if row['consumer']=='08001A10':
                for prefix in row.get('prefix_samples',['']):
                    f.draw(encode(prefix));u.mem_write(0x03001468,b'\xa5'*256)
                    for register,value in [(UC_ARM_REG_R0,0x02000000),(UC_ARM_REG_R1,ptr),(UC_ARM_REG_R4,0x02000000),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(register,value)
                    begin=int(row.get('inline_call_start','08001A10'),16)|1;end=int(row.get('inline_call_stop','0203FFF0'),16)
                    u.emu_start(begin,end,count=5000000)
                    if u.reg_read(UC_ARM_REG_PC)!=end or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Direct UI consumer return/stack mismatch')
                    if bytes(u.mem_read(0x03001468,256))!=b'\xa5'*256:raise ValueError('Direct UI consumer unexpectedly uses format scratch')
                    expected.draw(encode(prefix+text))
                    if f.pixels()!=expected.pixels():raise ValueError('Sequential direct UI label differs')
                    if len(prefix+text)>row['selected_max_cells']:raise ValueError('Combined direct UI label exceeds adopted width')
                    count+=1
                for index in row.get('getter_indices',[]):
                    u.reg_write(UC_ARM_REG_R0,index);u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
                    u.emu_start(int(row['getter'],16)|1,0x0203fff0,count=10000)
                    if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_R0)!=ptr:raise ValueError('Special unit label getter differs')
                continue
            if identity.endswith('-team'):samples=[('훌리오',),('캐로',),('가나다라마',),('가A나B다',),('???',)]
            elif identity=='save-time-single':samples=[(0,0),(1,9),(999,4),(19884,9)]
            elif identity=='save-time-double':samples=[(0,10),(12,59),(999,42),(19884,59)]
            else:samples=[()]
            for params in samples:
                u.mem_write(0x03000060,bytes(2048))
                if '%l' in text:f.draw(encode('이전 식재료\n남아 있으면 안 됨'))
                u.mem_write(0x02000000,bytes([1,1,31,30,1,1,0,13]))
                u.mem_write(0x03001468,b'\xa5'*256)
                values=list(params)
                if values and isinstance(values[0],str):
                    u.mem_write(0x02002000,encode(values[0])+b'\0');values[0]=0x02002000
                for register,value in [(UC_ARM_REG_R0,0x02000000),(UC_ARM_REG_R1,ptr),(UC_ARM_REG_R2,values[0] if values else 0),(UC_ARM_REG_R3,values[1] if len(values)>1 else 0),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(register,value)
                if row['consumer']=='080B0CD8':
                    # Original field caption wrapper fetches its window from
                    # 0200337C + 3C and takes the format string in r0.
                    u.mem_write(0x0200337c,struct.pack('<I',0x02001000))
                    u.mem_write(0x0200103c,bytes([1,1,31,30,1,1,0,13]))
                    u.reg_write(UC_ARM_REG_R0,ptr)
                    u.emu_start(0x080b0cd9,0x0203fff0,count=5000000)
                elif row['consumer']=='08001DA8':
                    u.emu_start(0x08001da9,0x0203fff0,count=5000000)
                else:raise ValueError('Unmodeled format consumer')
                if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Formatted consumer return/stack mismatch')
                rendered=text.replace('%l','\x10').replace('%0g','\x13\x00').replace('%1g','\x13\x01')
                # Actual formatter: 080027B2 emits clear/reset 10; 080027BE
                # emits icon 13 then its numeric argument (including zero).
                want=encode(rendered%params if params else rendered)
                buf=bytes(u.mem_read(0x03001468,256))
                if buf!=want+b'\0'+b'\xa5'*(255-len(want)):raise ValueError(f'Actual formatter content/extent mismatch {identity}: {params!r}')
                expected.draw(want)
                if expected.pixels()!=f.pixels():raise ValueError('Formatted rendering differs from exact selected text')
                count+=1
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'selected_ui_entries':len(profile),'format_and_pixel_mode_cases':count,'scope':'Real Thumb formatter or declared direct small-render path, including sequential team suffixes and special unit getter; representative boundaries in both modes; not all UI or whole-game coverage'}
    a.out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
