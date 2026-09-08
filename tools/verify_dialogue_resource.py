"""All indexed dialogue: exact instruction preservation and real name expansion."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from dialogue_structure import source_records,ROOT
from dialogue_tokens import expand_expected,unsafe_expansion_sequences
from text_codec import encode
from verify_small_consumer import Fixture

class Expander:
    def __init__(self,rom):
        self.u=Fixture(rom,0).uc;self.allocations=[];self.buf=0x02010000
        def allocate(u,address,size,data):
            self.allocations.append(u.reg_read(UC_ARM_REG_R0))
            u.reg_write(UC_ARM_REG_R0,self.buf);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        self.u.hook_add(UC_HOOK_CODE,allocate,begin=0x0800356c,end=0x0800356c)
        self.u.mem_write(0x02001d60,struct.pack('<I',0x02002000))
        self.u.mem_write(0x02003020,struct.pack('<II',0x02004000,0x02004040))
    def names(self,names):
        for key,address in [(b'@B',0x02002013),(b'@G',0x02002033),(b'@D',0x02002053),(b'@0',0x02004000),(b'@1',0x02004040)]:
            self.u.mem_write(address,names[key]+b'\0')
    def run(self,ptr,expected):
        u=self.u;self.allocations.clear();u.mem_write(self.buf-16,b'\xa5'*288)
        u.reg_write(UC_ARM_REG_R0,0x02003000);u.reg_write(UC_ARM_REG_R1,ptr)
        u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        u.emu_start(0x080c7669,0x0203fff0,count=1000000)
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00 or self.allocations!=[256] or u.reg_read(UC_ARM_REG_R0)!=self.buf:
            raise ValueError('Original expander allocation/return contract differs')
        want=b'\xa5'*16+expected+b'\0'+b'\xa5'*(271-len(expected))
        if len(expected)>=256 or bytes(u.mem_read(self.buf-16,288))!=want:raise ValueError('Expansion bytes, terminator or guard differ')

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--j',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();j=a.j.read_bytes();legacy=a.legacy.read_bytes();records=source_records(j,legacy)
    profile=json.loads((ROOT/'source/dialogue_profile.json').read_text(encoding='utf-8'))
    changes={int(r['record_offset'],0):r for r in json.loads((ROOT/'source/dialogue_fixes.json').read_text(encoding='utf-8'))['records']}
    for stream in profile['streams']:
        start=int(stream['start'],0);end=int(stream['end'],0);expected=bytearray(legacy[start:end])
        for off in changes:
            if start<=off<end:expected[off-start+4:off-start+8]=rom[off+4:off+8]
        if rom[start:end]!=expected:raise ValueError('Non-text VM instruction or operand changed')
    cases=[];legacy_unsafe=[]
    for row in records:
        off=row['record_offset'];oldptr=row['pointer'];ptr=struct.unpack_from('<I',rom,off+4)[0]
        if off not in changes and ptr!=oldptr:raise ValueError('Unselected dialogue pointer changed')
        start=ptr-0x08000000;raw=rom[start:rom.index(0,start)]
        oldstart=oldptr-0x08000000;oldraw=legacy[oldstart:legacy.index(0,oldstart)]
        if off not in changes and raw!=oldraw:raise ValueError('Unselected dialogue payload changed')
        if unsafe_expansion_sequences(raw):raise ValueError('Unsafe multibyte-trail macro remains')
        if unsafe_expansion_sequences(oldraw):legacy_unsafe.append((off,oldptr,oldraw))
        cases.append((ptr,raw))
    samples=[{k:encode(v) for k,v in zip((b'@B',b'@G',b'@D',b'@0',b'@1'),('훌리오','캐로','드림','크라토스','프레세아'))},
             {k:encode('가나다라마') for k in (b'@B',b'@G',b'@D',b'@0',b'@1')}]
    expander=Expander(rom);count=0;maximum=0
    for names in samples:
        expander.names(names)
        for ptr,raw in cases:
            expected=expand_expected(raw,names);maximum=max(maximum,len(expected))
            expander.run(ptr,expected);count+=1
    # Reproduce the two legacy failures with the untouched expander. This
    # proves the specific trail-byte mechanism, rather than just a regex hit.
    baseline=Expander(legacy);baseline.names(samples[0]);reproduced=[]
    for off,ptr,raw in legacy_unsafe:
        wrong=raw.replace(b'@B',samples[0][b'@B'])
        if wrong==expand_expected(raw,samples[0]):raise ValueError('Legacy fixture is not a trail-byte failure')
        baseline.run(ptr,wrong);reproduced.append(hex(off))
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'indexed_scripts':1000,'dialogue_records':len(records),'original_expander_cases':count,
            'maximum_observed_expanded_bytes':maximum,'allocation_bytes':256,'legacy_trail_byte_failures_reproduced':reproduced,
            'only_selected_dialogue_operands_changed':len(changes),'nontext_vm_instructions_preserved':True,
            'scope':'All indexed opcode0F and opcode25 dialogue payloads with default and five-Hangul name fixtures. Actual expander and strlen, allocator substituted. Not full script execution, layout, every possible custom string, or natural-play reachability.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
