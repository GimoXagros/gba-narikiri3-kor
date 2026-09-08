"""Execute emitted importer, original five-slot commit and delete in a CPU fixture.

This covers imported names, not a completed Hangul candidate keyboard.
"""
import argparse,json,hashlib,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode,hangul_map

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();f=Fixture(rom,0);u=f.uc
    u.mem_write(0x02003380,struct.pack('<I',0x02004000))
    u.mem_write(0x02004648,bytes([1,1,31,30,1,1,0,13]))
    def run(pc,r0,r1):
        u.reg_write(UC_ARM_REG_R0,r0);u.reg_write(UC_ARM_REG_R1,r1)
        u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        u.emu_start(pc|1,0x0203fff0,count=5000000)
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Name routine return/stack mismatch')
    def load(raw):
        u.mem_write(0x02002000,b'\xcc'*20+bytes(12))
        u.mem_write(0x02001000,raw+b'\0')
        run(0x080d6754,0x02002000,0x02001000)
    def commit():
        u.mem_write(0x02002800,b'\xa5'*32)
        run(0x080d66a8,0x02002000,0x02002800)
        data=bytes(u.mem_read(0x02002800,32))
        end=data.index(0)
        if data[end+1:]!=b'\xa5'*(31-end):raise ValueError('Commit overrun')
        return data[:end]
    cases=0
    for c in hangul_map().values():
        for pos in range(5):
            chars=['가']*5;chars[pos]=c;raw=encode(''.join(chars));load(raw)
            slots=bytes(u.mem_read(0x02002000,20))
            want=b''.join(encode(ch)+b'\0\0' for ch in chars)
            if slots!=want or bytes(u.mem_read(0x02002015,1))!=b'\x05':raise ValueError(f'Slot mapping mismatch {c} at {pos}')
            if commit()!=raw:raise ValueError(f'Commit mismatch {c} at {pos}')
            cases+=1
    samples=[encode('훌리오'),encode('캐로'),encode('드림호'),encode('가A나B다'),b'\x12\xb1\x12'+encode('한')+b'\xb6\xdeA',encode('가나다라마바')]
    for raw in samples:
        load(raw)
        count=bytes(u.mem_read(0x02002015,1))[0]
        if not 1<=count<=5:raise ValueError('Invalid imported count')
        before=bytes(u.mem_read(0x02002000,20))
        run(0x080d6630,0x02002000,0)
        after=bytes(u.mem_read(0x02002000,20))
        if after[:(count-1)*4]!=before[:(count-1)*4] or any(after[(count-1)*4:count*4]):raise ValueError('Delete damaged another character')
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'hangul_position_roundtrips':cases,'mixed_and_default_delete_cases':len(samples),'scope':'Actual Thumb importer, original five-slot commit and deletion; candidate keyboard and all persistence consumers are separate'}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
