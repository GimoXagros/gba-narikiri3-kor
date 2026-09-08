"""Classify original inactive UI paths without translating their bytes."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();profile=json.loads((ROOT/'source/auxiliary_exclusion_profile.json').read_text(encoding='utf-8'))
    parent=json.loads((ROOT/'source/internal_battle_menu_profile.json').read_text(encoding='utf-8'))
    for g in profile['guards']+parent['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[off:off+len(raw)]!=raw:raise ValueError('Inactive-path code guard differs')
    if hashlib.sha256(rom[0x7bf9f0:0x7bfd58]).hexdigest()!=profile['preserved_table_sha256']:raise ValueError('Internal actor series table changed')
    u32=lambda at:struct.unpack_from('<I',rom,at)[0]
    table=[(u32(0x7bfd10+i*8),u32(0x7bfd14+i*8)) for i in range(8)]
    series=[]
    for _,ptr in table[:7]:
        at=ptr-0x08000000;records=[]
        while u32(at):
            records.append((u32(at),struct.unpack_from('<h',rom,at+4)[0]));at+=8
        series.append(records)
    if len(table)!=8 or sum(map(len,series))!=93 or table[7][1]!=0 or u32(0x7bfd50)!=0:raise ValueError('Internal actor population/termination changed')
    f=Fixture(rom,0);u=f.uc;requests=[];expected_lists=[];menu_calls=[];callback_hits=[]
    callbacks=[u32(0x1127ac+i*8) for i in range(14)]
    def hook(uc,addr,size,_):
        if addr==0x08004a70:
            if not requests or not expected_lists:raise ValueError('Unexpected picker request')
            at=uc.reg_read(UC_ARM_REG_R3);got=[]
            for _ in range(64):
                ptr=int.from_bytes(uc.mem_read(at,4),'little');at+=4
                if ptr==0:break
                got.append(ptr)
            else:raise ValueError('Picker list missing terminator')
            if got!=expected_lists.pop(0):raise ValueError('Real internal list copier changed identity/order')
            menu_calls.append(got);uc.reg_write(UC_ARM_REG_R0,requests.pop(0)&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        elif addr in [c&~1 for c in callbacks]:
            callback_hits.append(addr|1);uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        elif addr in (0x08000814,0x08001694,0x08001da8,0x08001754,0x08000830):raise ValueError('Inactive hardware error path executed')
    handle=u.hook_add(UC_HOOK_CODE,hook)
    def run(pc):
        u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        u.emu_start(pc|1,0x0203fff0,count=5000000)
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Inactive path return/stack mismatch')
    actions=0
    for i,callback in enumerate(callbacks):
        requests[:]=[i];expected_lists[:]=[[u32(0x1127a8+j*8) for j in range(14)]];callback_hits.clear();run(0x0800c550)
        if requests or expected_lists or callback_hits!=[callback]:raise ValueError('Internal top-level action dispatch differs')
        actions+=1
    # C5FC itself is not one of the substituted editor action callbacks.
    # Its body executes normally and its nested pickers receive
    # deterministic CPU inputs. No game actor state is written by this getter.
    cases=0
    for s,records in enumerate(series):
        for index,(_,ident) in enumerate(records):
            requests[:]=[s,index];expected_lists[:]=[[x[0] for x in table],[x[0] for x in records]]
            run(0x0800c5fc)
            if requests or expected_lists or u.reg_read(UC_ARM_REG_R0)!=ident:raise ValueError('Internal actor picker ID differs')
            cases+=1
        requests[:]=[s,-1];expected_lists[:]=[[x[0] for x in table],[x[0] for x in records]];run(0x0800c5fc)
        if requests or expected_lists or u.reg_read(UC_ARM_REG_R0)!=0xffffffff:raise ValueError('Internal actor submenu cancel differs')
        cases+=1
    for choice,want in ((-1,0xffffffff),(7,0)):
        requests[:]=[choice];expected_lists[:]=[[x[0] for x in table]];run(0x0800c5fc)
        if requests or expected_lists or u.reg_read(UC_ARM_REG_R0)!=want:raise ValueError('Internal series cancel/none differs')
        cases+=1
    hardware=0
    for value in (0,1,0xffffffff,0x55555555,0xaaaaaaaa):
        for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3):u.reg_write(reg,value)
        run(0x08004cc0);hardware+=1
    u.hook_del(handle)
    report={'status':'SCOPED_INACTIVE_PATH_CLASSIFICATION_PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'preserved_internal_action_labels':14,'original_action_dispatch_cases':actions,'preserved_actor_alias_entries':93,'series_entries':8,'original_actor_selection_and_cancel_cases':cases,'hardware_constant_success_cases':hardware,'scope':'Internal C550 actions and C6A8->C5FC actor lists are owned by the already guarded fifth ordinary battle action; CPU picker and leaf-action stubs only. 4CBC always returns 1, so 4CC0 skips its Japanese hardware-error message. No ROM bytes changed; not a proof about cheats, arbitrary memory modification, all hidden entry points or entire text population.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
