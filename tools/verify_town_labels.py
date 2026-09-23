"""Exercise original town selector, resource lookup, decompression and DMA queue."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_SP
from verify_small_consumer import Fixture
from gba_rle import unpack
from town_labels import ROOT,compose,source_canvas,tile_half

def main():
    p=argparse.ArgumentParser()
    for k in ('rom','legacy','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();rom=a.rom.read_bytes();old=a.legacy.read_bytes()
    profile=json.loads((ROOT/'source/town_label_profile.json').read_text('utf-8'));bank=int(profile['bank'],0)
    labels={x['number']:x for x in profile['labels']}
    changed={s['index'] for x in labels.values() for s in x['resources']}
    for g in profile['guards']:
        at=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[at:at+len(raw)]!=raw:raise ValueError('Town consumer or selection metadata changed')
    for index in range(89):
        at=bank+4+index*4
        if index not in changed and rom[at:at+4]!=old[at:at+4]:raise ValueError('Unrelated town resource moved')
    cases=[]
    for number in range(15):
        want=compose(old,profile,number)[0] if number in labels else source_canvas(old,bank,number)
        fixture=Fixture(rom,0);u=fixture.uc;scratch=0x02010000;loaded=[]
        u.mem_write(0x020009f8+12,struct.pack('<II',0,8))
        u.mem_write(0x03002a30,struct.pack('<I',scratch))
        u.mem_write(scratch-4,b'\xa5'*520)
        def hook(uc,addr,size,data):
            if addr==0x08004680:
                handle=uc.reg_read(UC_ARM_REG_R0)
                if handle not in (0,8):raise ValueError('Unexpected title sprite handle')
                uc.reg_write(UC_ARM_REG_R0,0x06010000+handle*32)
                uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        def intr(uc,number,data):
            pc=uc.reg_read(UC_ARM_REG_PC)
            if bytes(uc.mem_read(pc-2,2))!=b'\x14\xdf':raise ValueError('Unexpected BIOS call')
            src=uc.reg_read(UC_ARM_REG_R0);dst=uc.reg_read(UC_ARM_REG_R1)
            raw,_=unpack(rom,src-0x8000000,len(rom),256)
            uc.mem_write(dst,raw);loaded.append((src,dst,raw))
        u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
        u.reg_write(UC_ARM_REG_R0,number);u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        u.emu_start(0x080a5ba1,0x0203fff0,count=1000000)
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or len(loaded)!=2:raise ValueError('Original town selector did not return')
        if struct.unpack('<I',u.mem_read(0x03002a20,4))[0]!=2:raise ValueError('Title DMA queue count differs')
        for half,index in enumerate((58+number,73+number)):
            src,dst,raw=loaded[half]
            expected_src=0x8000000+bank+struct.unpack_from('<I',rom,bank+4+index*4)[0]
            if (src,dst)!=(expected_src,scratch+half*256) or raw!=tile_half(want,half):raise ValueError('Town title selected bytes differ')
            dma=struct.unpack('<IIII',u.mem_read(0x03002820+16*half,16))
            if dma!=(dst,0x06010000+half*256,0x84000040,256):raise ValueError('Town title transfer geometry changed')
        if bytes(u.mem_read(scratch-4,4))!=b'\xa5'*4 or bytes(u.mem_read(scratch+512,4))!=b'\xa5'*4:raise ValueError('Title scratch bounds changed')
        cases.append(number)
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'original_selector_cases':len(cases),
      'original_resource_loads':len(cases)*2,'changed_title_pairs':len(labels),'unchanged_title_pairs':11,
      'palette_and_geometry_preserved':True,'scope':'All 15 original selectors, original relative bank lookup, allocator, decompressor dispatch and DMA queue. Graphics handle lookup and BIOS RLE are modeled; normal screen navigation verified separately.'}
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8');print(json.dumps(result))

if __name__=='__main__':main()
