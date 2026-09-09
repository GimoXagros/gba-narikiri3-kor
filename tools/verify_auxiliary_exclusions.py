"""Classify original inactive UI paths without translating their bytes."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
ROOT=Path(__file__).resolve().parents[1]


def verify_editor_leaves(rom, profile):
    """Execute two editor bodies; substitute only their interactive pickers."""
    u32=lambda at:struct.unpack_from('<I',rom,at)[0]
    for t in profile['editor_leaf_tables']:
        base=int(t['table'],0);n=t['count']
        if u32(base+n*4)!=0 or hashlib.sha256(rom[base:base+n*4]).hexdigest()!=t['table_sha256']:
            raise ValueError('Internal leaf table changed')
        action=u32(0x1127ac+t['guarded_internal_action_index']*8)
        if action!=int(t['action_pointer'],0) or action!=0x08000001+int(t['consumer'],0):
            raise ValueError('Internal leaf ownership changed')
    f=Fixture(rom,0);u=f.uc;queue=[];calls=[]
    scope=0x02001000;actors=[0x02002000+i*0x200 for i in range(3)]
    def picker(uc,addr,size,_):
        if addr not in (0x08004a70,0x08004b4c):return
        if not queue:raise ValueError('Unexpected internal leaf picker')
        want_addr,table,count,answer=queue.pop(0)
        if addr!=want_addr:raise ValueError('Internal picker sequence differs')
        if addr==0x08004a70:
            base=uc.reg_read(UC_ARM_REG_R3)
            got=[]
            for i in range(32):
                ptr=int.from_bytes(uc.mem_read(base+4*i,4),'little')
                if ptr==0:break
                got.append(ptr)
            else:raise ValueError('Missing internal leaf list terminator')
            want=[u32(table+4*i) for i in range(count)]
            if base!=0x08000000+table or got!=want:
                raise ValueError('Internal leaf picker table differs')
        else:
            sp=uc.reg_read(UC_ARM_REG_SP)
            args=struct.unpack('<II',uc.mem_read(sp,8))
            if args!=(10,0x0800c999) or [uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]!=[2,1,16,10]:
                raise ValueError(f'Internal B-button technique picker differs: {args}')
        calls.append(addr);uc.reg_write(UC_ARM_REG_R0,answer&0xffffffff)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    handle=u.hook_add(UC_HOOK_CODE,picker)
    def run(pc,requests,changes):
        queue[:]=requests
        u.mem_write(0x020031a0,struct.pack('<I',scope))
        u.mem_write(scope,b'\0'*0x200)
        u.mem_write(scope+0xf0,struct.pack('<I',actors[0]))
        u.mem_write(scope+0x104,struct.pack('<III',*actors))
        expected=bytearray(b'\x55'*0x600)
        for actor,index,value in changes:expected[actor*0x200+index]=value
        u.mem_write(actors[0],b'\x55'*0x600)
        u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        u.emu_start(pc|1,0x0203fff0,count=100000)
        if queue or u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00 or u.reg_read(UC_ARM_REG_R0)!=0:
            raise ValueError('Internal leaf return/stack/input differs')
        if bytes(u.mem_read(actors[0],0x600))!=expected:
            raise ValueError('Internal leaf changed unintended actor bytes')
    b=lambda answer:(0x08004a70,0x7c0398,4,answer)
    technique=lambda answer:(0x08004b4c,None,10,answer)
    actor=lambda answer:(0x08004a70,0x7c03e4,3,answer)
    strategy=lambda answer:(0x08004a70,0x7c03f4,5,answer)
    button_cases=0;strategy_cases=0
    for slot in range(4):
        for skill in range(10):
            run(0x0800c9d0,[b(slot),technique(skill),b(-1)],[(0,0x90+slot,u32(0x7c03ac+skill*4))]);button_cases+=1
        run(0x0800c9d0,[b(slot),technique(-1),b(-1)],[]);button_cases+=1
    run(0x0800c9d0,[b(-1)],[]);button_cases+=1
    for who in range(3):
        for choice in range(5):
            run(0x0800ca98,[actor(who),strategy(choice),actor(-1)],[(who,0xf5,choice)]);strategy_cases+=1
        run(0x0800ca98,[actor(who),strategy(-1),actor(-1)],[]);strategy_cases+=1
    run(0x0800ca98,[actor(-1)],[]);strategy_cases+=1
    u.hook_del(handle)
    return {'preserved_labels':9,'b_button_assign_and_cancel_cases':button_cases,'strategy_assign_and_cancel_cases':strategy_cases,'actual_leaf_picker_calls':len(calls),'whole_actor_guard_bytes_per_case':0x600,'scope':'Original C9D0/CA98 bodies, table identity, assignment bytes and cancellation. Only interactive pickers substituted. Their ownership is the guarded C550 internal editor; not a claim about every hidden entry point.'}


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
    report['editor_leaf_verification']=verify_editor_leaves(rom,profile)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
