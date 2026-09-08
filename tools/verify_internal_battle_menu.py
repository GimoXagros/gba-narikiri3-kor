"""Prove the ordinary four-item battle selector cannot choose its debug slot."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();profile=json.loads((ROOT/'source/internal_battle_menu_profile.json').read_text(encoding='utf-8'))
    for g in profile['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[off:off+len(raw)]!=raw:raise ValueError('Original battle selection boundary differs')
    start,end=int(profile['duplicate_table_start'],0),int(profile['duplicate_table_end'],0)
    if hashlib.sha256(rom[start:end]).hexdigest()!=profile['duplicate_table_sha256']:raise ValueError('Internal-only duplicate table was changed')
    ptrs=struct.unpack_from('<213I',rom,start)
    if ptrs[-1]!=0 or any(not 0x08000000<=p<0x09000000 for p in ptrs[:-1]):raise ValueError('Internal null-terminated list differs')
    f=Fixture(rom,0);u=f.uc;context=0x02008000;targets=[];stubs=[]
    table=struct.unpack_from('<5I',rom,0x7c1d08)
    if table[4]!=0x08017ac1:raise ValueError('Internal fifth dispatch identity differs')
    def hook(uc,addr,size,_):
        if addr in (0x080dbecc,0x08017bdc):
            stubs.append(addr);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        elif addr in [p&~1 for p in table]:
            targets.append(addr|1);uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def run(pc):
        u.reg_write(UC_ARM_REG_R0,context);u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        u.emu_start(pc|1,0x0203fff0,count=10000)
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Battle selector CPU did not return')
    cases=0
    for index in [0,1,2,3,-32768,-1,4,32767]:
        for pressed in range(16):
            # Every combination of A/B/right/left. Direction processing and
            # the original signed clamp run before confirmation dispatch.
            keys=(pressed&3)|((pressed&12)<<2)
            u.mem_write(context,bytes(0x40));u.mem_write(context+10,struct.pack('<h',index));u.mem_write(0x030033f8,struct.pack('<H',keys))
            run(0x08017668)
            chosen=struct.unpack('<h',u.mem_read(context+10,2))[0]
            if not 0<=chosen<=3:raise ValueError('Ordinary selector allowed internal fifth slot')
            if u.reg_read(UC_ARM_REG_R0)==2:
                before=len(targets);run(0x080176f0)
                if targets[before:]!=[table[chosen]]:raise ValueError('Actual dispatch did not select ordinary action')
            cases+=1
    if table[4] in targets:raise ValueError('Internal editor was dispatched')
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'selector_boundary_cases':cases,'actual_dispatch_cases':len(targets),'ordinary_actions':[hex(v) for v in table[:4]],'unselectable_internal_action':hex(table[4]),'preserved_duplicate_name_entries':212,'scope':'Original ordinary battle menu clamps selection to 0..3 before confirming; fifth slot 17AC0 opens internal character editor C5DC/C6A8 with duplicate 212-entry list. Sound and cursor animation substituted. This is a scoped ordinary-route exclusion, not a proof against arbitrary memory corruption, cheats, all hidden code or every ROM reference.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
