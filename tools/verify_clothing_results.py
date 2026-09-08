"""Clothing-only width, original creation path and signed stat-result buffers."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode,hangul_map
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();old=a.legacy.read_bytes();profile=json.loads((ROOT/'source/clothing_result_profile.json').read_text(encoding='utf-8'))
    texts={r['id']:r['text'] for r in json.loads((ROOT/'translations/clothing_results.json').read_text(encoding='utf-8'))['records']}
    modified=set(range(0xd42a8,0xd42b0))
    for row in profile['records']:
        at=int(row['pointer_offset'],0);modified.update(range(at,at+4));ptr=struct.unpack_from('<I',rom,at)[0]-0x08000000
        if not 0x10e0000<=ptr<0x10e1000 or rom[ptr:rom.index(0,ptr)]!=encode(texts[row['id']]):raise ValueError('Clothing selected field differs')
    for g in profile['guards']:
        at=int(g['offset'],0)
        for i,value in enumerate(bytes.fromhex(g['hex'])):
            if at+i not in modified and rom[at+i]!=value:raise ValueError('Clothing unrelated code or data changed')
    for i in range(123):
        at=0x105758+i*24
        if rom[at+8:at+24]!=old[at+8:at+24]:raise ValueError('Item data or signed clothing stat values changed')
    measure_cases=0;legacy_cases=0;creation_cases=0;stat_records=0;stat_messages=0;max_buffer=0;boundary_records=0
    for mode in (0,1):
        f=Fixture(rom,mode);expected=Fixture(rom,mode);previous=Fixture(old,mode);u=f.uc
        def run(pc,r0=0,r1=0):
            for reg,val in [(UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,val)
            u.emu_start(pc|1,0x0203fff0,count=5000000)
            if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Clothing caller return/stack differs')
            return u.reg_read(UC_ARM_REG_R0)
        for char in hangul_map().values():
            raw=encode('ABC '+char+' 9');u.mem_write(0x02002000,raw+b'\0')
            if run(0x080d42a8,0x02002000)!=7:raise ValueError('Hangul visible width is incorrect')
            measure_cases+=1
        for raw in [b'',b'ABC 123',b'\x12'+bytes.fromhex('b6de')+b'\x12',bytes.fromhex('cadecbdeccdecddecadecadf'),b'\x10\x11\x12\nABC']:
            u.mem_write(0x02002000,raw+b'\0');now=run(0x080d42a8,0x02002000)
            q=previous.uc;q.mem_write(0x02002000,raw+b'\0');q.reg_write(UC_ARM_REG_R0,0x02002000);q.reg_write(UC_ARM_REG_SP,0x03007e00);q.reg_write(UC_ARM_REG_LR,0x0203fff1);q.emu_start(0x080d42a9,0x0203fff0,count=10000)
            if now!=q.reg_read(UC_ARM_REG_R0):raise ValueError('Legacy kana/control width convention changed')
            legacy_cases+=1
        y=17 if mode else 18
        def reset():
            u.mem_write(0x03000060,bytes(2048))
            # Exact original 16E8 x3/y17/width24/height1 layout.
            u.mem_write(0x02000000,bytes([3,17,27,19,3,y,1,13]))
        actors=json.loads((ROOT/'translations/actors.json').read_text(encoding='utf-8'))['records']
        for i,row in enumerate(actors):
            reset();run(0x080d42c8,0x02000000,i)
            rendered=texts['creation']%row['compact'];x=3+(24-len(rendered))//2
            expected.draw(encode(rendered),x=x,y=y,mark_mode=1)
            if f.pixels()!=expected.pixels():raise ValueError(f'Centered clothing creation pixels differ for actor {i}, mode {mode}')
            if bytes(u.mem_read(0x02000000,4))!=bytes([3,17,27,19]):raise ValueError('Creation window bounds changed')
            creation_cases+=1
        observed=[];selected_item=0;active_deltas=[];synthetic=False
        def hook(uc,address,size,_):
            nonlocal stat_messages,max_buffer
            if address==0x080065bc and synthetic:
                # Separate CPU-only signed-byte boundary fixture. The ROM
                # and all real item records remain untouched.
                uc.reg_write(UC_ARM_REG_R0,0x02005000);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            elif address==0x08008db8:
                # Only the original 90-frame presentation wait is skipped.
                if uc.reg_read(UC_ARM_REG_R0)!=90:raise ValueError('Unexpected clothing presentation delay')
                uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            elif address==0x080d4354:
                index=uc.reg_read(UC_ARM_REG_R7);delta=active_deltas[index]
                label=['HP','TP',texts['attack'],texts['defense'],texts['intellect'],texts['agility']][index]
                want=encode(texts['increase' if delta>0 else 'decrease']%(label,abs(delta)))
                sp=uc.reg_read(UC_ARM_REG_SP);actual=bytes(uc.mem_read(sp,32));end=actual.index(0)
                if actual[:end]!=want or end>=32:raise ValueError('Original clothing formatter content/buffer differs')
                max_buffer=max(max_buffer,end+1);observed.append((label,delta,want));stat_messages+=1
            elif address==0x080d4380:
                label,delta,want=observed[-1]
                visible=len(texts['increase' if delta>0 else 'decrease']%(label,abs(delta)));x=3+(24-visible)//2
                # Original 17A0 redraws the border in mode 1 and resets its
                # baseline to y+1. Preserve that behavior in the reference;
                # a blank-map-only fixture would incorrectly reject it.
                q=expected.uc;q.mem_write(0x03000060,bytes(2048));q.mem_write(0x02000000,bytes([3,17,27,19,3,y,1,13]))
                for reg,val in [(UC_ARM_REG_R0,0x02000000),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:q.reg_write(reg,val)
                q.emu_start(0x080017a1,0x0203fff0,count=1000000)
                if q.reg_read(UC_ARM_REG_PC)!=0x0203fff0:raise ValueError('Reference window clear did not return')
                baseline=q.mem_read(0x02000005,1)[0]
                expected.draw(want,clear=False,x=x,y=baseline,mark_mode=1)
                if f.pixels()!=expected.pixels():
                    differences=[(xx,yy) for yy in range(32) for xx in range(32) if f.tile(xx,yy)!=expected.tile(xx,yy)]
                    raise ValueError(f'Clothing stat-result center/pixels differ for item {selected_item} {label} {delta}: window {bytes(uc.mem_read(0x02000000,8)).hex()}, expected x/y {x}/{y}, differing tiles {differences[:40]}')
        handle=u.hook_add(UC_HOOK_CODE,hook)
        saved_regs=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8]
        for i in range(123):
            selected_item=i;reset();observed.clear()
            active_deltas=list(struct.unpack_from('6b',rom,0x105758+i*24+18))
            for n,reg in enumerate(saved_regs):u.reg_write(reg,0x51515151+n)
            run(0x080d430c,0x02000000,i)
            if [u.reg_read(reg) for reg in saved_regs]!=[0x51515151+n for n in range(len(saved_regs))]:raise ValueError('Clothing stat scratch damaged saved registers')
            record=rom[0x105758+i*24+18:0x105758+i*24+24]
            if len(observed)!=sum(v!=0 for v in record):raise ValueError('Original six-stat loop/zero skip differs')
            stat_records+=1
        synthetic=True
        for delta in (-128,-1,0,1,127):
            selected_item=f'synthetic {delta}';active_deltas=[delta]*6;reset();observed.clear()
            u.mem_write(0x02005000,bytes(18)+struct.pack('6b',*active_deltas))
            for n,reg in enumerate(saved_regs):u.reg_write(reg,0x51515151+n)
            run(0x080d430c,0x02000000,0)
            if [u.reg_read(reg) for reg in saved_regs]!=[0x51515151+n for n in range(len(saved_regs))]:raise ValueError('Signed boundary formatting damaged stack/registers')
            if len(observed)!=(6 if delta else 0):raise ValueError('Signed boundary branch/zero skip differs')
            boundary_records+=1
        u.hook_del(handle)
    r={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'selected_text_fields':7,'hangul_measure_cases':measure_cases,'legacy_width_cases':legacy_cases,'actual_creation_cases':creation_cases,'actual_item_stat_record_cases':stat_records,'synthetic_signed_boundary_records':boundary_records,'stat_messages_including_boundaries':stat_messages,'maximum_observed_stack_string_bytes':max_buffer,'original_stack_buffer_bytes':32,'item_stat_data_preserved':True,'scope':'Actual original creation getter/center/renderer and 123-item six-signed-stat loop with only its 90-frame wait substituted, both modes. Separate signed-byte boundary fixture substitutes item getter with a RAM record, never changing ROM/saves. Every Hangul width and original legacy convention checked. Normal wardrobe crafting remains separate.'}
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))


if __name__=='__main__':main()
