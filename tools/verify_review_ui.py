"""Verify guarded non-dialogue text pointers and shared glyph rendering."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_SP

from review_ui_text import validate,source_string,TOKEN
from text_codec import encode,decode
from verify_small_consumer import Fixture
from verify_skill_text import glyphs


def verify_status_separator(rom,text):
    # 08009AB4 composes the actual item-effect status line. The original
    # separator is 、; the user selected a comma in Korean. Checking the
    # standalone string alone would miss a change in the combined output.
    if text != ',상태　회복' or not encode(text).startswith(b','):
        raise ValueError('Status separator is not the requested comma')
    expected=encode('ＨＰ30％회복'+text)
    for mode in (0,1):
        fixture=Fixture(rom,mode);u=fixture.uc
        stack,record=0x03007000,0x02003000
        u.mem_write(record,b'\0'*16)
        u.mem_write(record+0xd,bytes([30,0,1]))
        u.mem_write(record+8,struct.pack('<I',0x02005000))
        u.mem_write(0x02005000,b'check\0')
        u.reg_write(UC_ARM_REG_R4,record)
        u.reg_write(UC_ARM_REG_SP,stack)
        u.emu_start(0x08009ab5,0x08001660,count=5000000)
        if u.reg_read(UC_ARM_REG_PC)!=0x08001660:
            raise ValueError('Original status composer did not reach its display caller')
        combined=bytes(u.mem_read(stack,len(expected)+1))
        if combined!=expected+b'\0':
            raise ValueError('Original status composer lost comma separator')
        # Render the composed text through the original 12x16 large-font
        # consumer. The first separator must occupy cell 7 and the following
        # status glyph must begin in cell 8, in both font modes.
        drawn=[]
        def observe(uc,address,size,data):
            drawn.append(tuple(uc.reg_read(reg) for reg in
                               (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)))
        u.hook_add(UC_HOOK_CODE,observe,begin=0x08001414,end=0x08001414)
        u.mem_write(0x02006000,expected+b'\0')
        u.mem_write(0x03000040,bytes([0,0,18,2,0,0,0,13,1,28,15,4,0,0,0,0]))
        u.mem_write(0x03000560,bytes(0xf00))
        background=11 if mode else 0
        u.mem_write(0x03001464,bytes([background*17,background*16+15,240+background,255]))
        u.reg_write(UC_ARM_REG_R0,0x02006000)
        u.reg_write(UC_ARM_REG_R1,0)
        u.reg_write(UC_ARM_REG_SP,0x03007e00)
        u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        u.emu_start(0x08001661,0x0203fff0,count=5000000)
        comma_at=len('ＨＰ30％회복')
        if (u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or len(drawn)!=len('ＨＰ30％회복'+text)
                or drawn[comma_at]!=(comma_at,0,glyphs(b',')[0])
                or drawn[comma_at+1][0]!=comma_at+1):
            raise ValueError('Comma status separator did not occupy one rendered cell')
    return 2,2


def main():
    p=argparse.ArgumentParser()
    for key in ('rom','j','legacy','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    rom,j,k=a.rom.read_bytes(),a.j.read_bytes(),a.legacy.read_bytes()
    profile,catalog=validate(j,k)
    if len(rom)!=0x2000000:raise ValueError('UI review target is not 32 MiB')
    chosen={r['stable_id']:r['text'] for r in catalog['records']}
    targets={}
    for row in profile['fields']:
        at=int(row['pointer_offset'],0);ptr=struct.unpack_from('<I',rom,at)[0]
        if not 0x09141000<=ptr<0x09150000:
            raise ValueError('UI review pointer outside reserved pool: '+row['stable_id'])
        text=chosen[row['stable_id']]
        if source_string(rom,ptr)!=encode(text) or decode(source_string(rom,ptr),True)!=text:
            raise ValueError('UI review target text differs: '+row['stable_id'])
        targets[row['stable_id']]=ptr
    status_composer_cases,status_renderer_cases=verify_status_separator(rom,chosen['xlsx-32'])
    cases=0
    for mode in (0,1):
        fixture=Fixture(rom,mode)
        for identity,text in chosen.items():
            for line in text.split('\n'):
                visible=TOKEN.sub('',line)
                if not visible:continue
                fixture.draw(encode(visible),x=1,y=1)
                if fixture.tile(len(visible),1)==bytes(32):
                    raise ValueError('UI review final visible glyph missing: '+identity)
                cases+=1
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),
        'source_pointer_fields':len(profile['fields']),'target_text_reextractions':len(targets),
        'shared_renderer_line_cases':cases,'status_separator_original_composer_cases':status_composer_cases,
        'status_separator_large_renderer_cases':status_renderer_cases,
        'scope':'Exact original pointer/string guards, approved target bytes, preserved format tokens and line structure, 18-cell static width, shared font-renderer glyph checks, and the actual 08009AB4 status-effect text composer. Individual natural UI navigation remains separate.'}
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
