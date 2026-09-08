"""Actual character-library flag/list consumers and large-font placement."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode,decode,glyph_index
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();old=a.legacy.read_bytes();base=0x1c06e0
    profile=json.loads((ROOT/'source/biography_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/biographies.json').read_text(encoding='utf-8'))
    for g in profile['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[off:off+len(raw)]!=raw:raise ValueError('Library code/controls changed')
    selected=0
    for row in catalog['records']:
        i=row['index'];fields={f['slot']:f for f in row['fields']}
        if rom[base+i*24+20:base+(i+1)*24]!=old[base+i*24+20:base+(i+1)*24]:raise ValueError('Library sprite/unlock ID changed')
        for slot in range(5):
            off=base+i*24+slot*4;ptr=struct.unpack_from('<I',rom,off)[0]-0x08000000
            if slot in fields:
                text=fields[slot]['text']
                if not 0x10d0000<=ptr<0x10e0000 or rom[ptr:rom.index(0,ptr)]!=encode(text):raise ValueError('Library relocated string differs')
                selected+=1
            elif rom[off:off+4]!=old[off:off+4]:raise ValueError('Unselected library field changed')
    small_cases=0;large_cases=0;glyph_cases=0;max_cells=0
    for mode in (0,1):
        f=Fixture(rom,mode);expected=Fixture(rom,mode);u=f.uc
        u.mem_write(0x02001d68,struct.pack('<I',0x02009000))
        def run(pc,r0,r1=0):
            for reg,value in [(UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,value)
            u.emu_start(pc|1,0x0203fff0,count=5000000)
            if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Library CPU return/stack differs')
        for unlocked in (False,True):
            u.mem_write(0x02009000,(b'\xff' if unlocked else b'\0')*400)
            for row in catalog['records']:
                i=row['index'];name=next(fld['text'] for fld in row['fields'] if fld['slot']==0)
                f.draw(b'');run(0x080cf304,0x02000000,i)
                expected.draw(encode(f'{i+1:3d} '+(name if unlocked else '????')))
                if f.pixels()!=expected.pixels():raise ValueError('Original unlocked/hidden library list differs')
                small_cases+=1
        drawn=[]
        def hook(uc,addr,size,_):
            if addr==0x08001414:drawn.append(tuple(uc.reg_read(reg) for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)))
        handle=u.hook_add(UC_HOOK_CODE,hook)
        for row in catalog['records']:
            i=row['index']
            for slot in range(1,5):
                ptr=struct.unpack_from('<I',rom,base+i*24+slot*4)[0];at=ptr-0x08000000
                raw=rom[at:rom.index(0,at)];text=decode(raw,True)
                if '%' in text or len(text)>36:raise ValueError('Biography exceeds inspected two-row dialogue window')
                # Observed 18-column, two-row library dialogue geometry.
                # Zero per-character delay avoids a fixture VBlank wait;
                # normal runtime validates the unchanged key-wait separators.
                u.mem_write(0x03000040,bytes([0,0,18,2,0,0,0,13,1,28,15,4,0,0,0,0]))
                u.mem_write(0x0300055c,b'\xa5'*4);u.mem_write(0x03001464,b'\xa5'*4)
                drawn.clear();run(0x08001660,ptr)
                if bytes(u.mem_read(0x0300055c,4))!=b'\xa5'*4 or bytes(u.mem_read(0x03001464,4))!=b'\xa5'*4:raise ValueError('Large font buffer boundary changed')
                codes=[]
                for char in text:
                    # The original large renderer expands printable ASCII to
                    # its full-width font slot. Compare to CP932 full width,
                    # independently of the runtime conversion implementation.
                    # Original ASCII period maps to Japanese full stop 8142,
                    # not the full-width European period 8144.
                    full={' ':'　','.':'。',',':'、'}.get(char,chr(ord(char)+0xfee0) if '!'<=char<='~' else char)
                    code=encode(full)
                    if len(code)!=2:raise ValueError('Unmodeled large glyph')
                    codes.append(glyph_index(int.from_bytes(code,'big')))
                want=[(n%18,n//18,index) for n,index in enumerate(codes)]
                if drawn!=want:raise ValueError(f'Large library glyph/position differs at record {i} field {slot}: {drawn!r} != {want!r}')
                large_cases+=1;glyph_cases+=len(codes);max_cells=max(max_cells,len(codes))
        u.hook_del(handle)
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'library_records':37,'selected_string_fields':selected,'original_flag_and_list_cases':small_cases,'large_field_consumer_cases':large_cases,'large_glyph_position_cases':glyph_cases,'maximum_large_field_cells':max_cells,'metadata_and_newline_keywait_code_preserved':True,'scope':'Actual 37-entry locked/unlocked list through original flag getter and formatter, both small modes. Every four-line biography field uses original large formatter/converter/pixel routine with inspected 18x2 geometry and zero fixture character delay. Whole biography paging and normal unlock progression need runtime review.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
