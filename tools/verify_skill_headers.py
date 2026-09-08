"""Run original header dispatch, resource loader and DMA queue in a CPU fixture."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();old=a.legacy.read_bytes();profile=json.loads((ROOT/'source/skill_header_profile.json').read_text(encoding='utf-8'))
    glyphs=json.loads((ROOT/'fonts/dalmoori-wansung.json').read_text(encoding='utf-8'))
    for g in profile['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[off:off+len(raw)]!=raw:raise ValueError('Header consumer/layout changed')
    bank=int(profile['bank'],0)
    for idx in range(111):
        if idx in (45,46,47,48):continue
        off=bank+4+idx*4
        if rom[off:off+4]!=old[off:off+4]:raise ValueError('Unrelated graphics bank entry moved')
    pixel_cases=0;loads=0;cases=[]
    for kind,anchor,ids,text in [(3,48,[45,46,47],'특기 설정'),(4,68,[45,48],'특기 사용')]:
        f=Fixture(rom,0);u=f.uc;allocation=[];composites=[];decompressed=[]
        scratch=0x02010000
        u.mem_write(0x02003380,struct.pack('<I',0x02008000))
        u.mem_write(0x03002a30,struct.pack('<I',scratch));u.mem_write(scratch-4,b'\xa5'*1024)
        # Real graphics allocator is represented by one isolated contiguous
        # OBJ tile extent. The compositor is observed at its call boundary;
        # all dispatch, shape-size lookup, loads and DMA queue code execute.
        def hook(uc,addr,size,_):
            if addr==0x080045ec:
                allocation.append(uc.reg_read(UC_ARM_REG_R0));uc.reg_write(UC_ARM_REG_R0,196)
                uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            elif addr==0x08002a30:
                composites.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)])
                uc.reg_write(UC_ARM_REG_R0,0x02008000);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        def intr(uc,number,_):
            pc=uc.reg_read(UC_ARM_REG_PC)
            if bytes(uc.mem_read(pc-2,2))!=b'\x14\xdf':raise ValueError('Unexpected BIOS operation')
            source=uc.reg_read(UC_ARM_REG_R0);dest=uc.reg_read(UC_ARM_REG_R1)
            header=struct.unpack('<I',uc.mem_read(source,4))[0]
            if header!=0x8030:raise ValueError('Header size or compression type changed')
            out=bytearray();cursor=source+4
            while len(out)<128:
                flag=uc.mem_read(cursor,1)[0];cursor+=1
                length=(flag&127)+3 if flag&128 else flag+1
                if len(out)+length>128:raise ValueError('New RLE block exceeds declared output')
                if flag&128:
                    out.extend(bytes(uc.mem_read(cursor,1))*length);cursor+=1
                else:out.extend(uc.mem_read(cursor,length));cursor+=length
            uc.mem_write(dest,bytes(out));decompressed.append((source,dest,bytes(out)))
        u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
        for reg,value in [(UC_ARM_REG_R0,kind),(UC_ARM_REG_R1,anchor),(UC_ARM_REG_R2,0),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,value)
        try:u.emu_start(0x080c90f9,0x0203fff0,count=100000)
        except Exception as exc:raise ValueError('Header CPU fixture failed at '+hex(u.reg_read(UC_ARM_REG_PC))) from exc
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Header path did not return cleanly')
        if allocation!=[len(ids)*4] or len(composites)!=1 or len(decompressed)!=len(ids):raise ValueError('Header allocation/loading differs')
        x,y,ptr,tile=composites[0]
        if (x,y,tile)!=(anchor,0,196):raise ValueError('Original header anchor/allocation differs')
        frames,desc=struct.unpack('<II',u.mem_read(ptr,8))
        n=struct.unpack('<I',u.mem_read(desc,4))[0]
        if (frames,n)!=(1,len(ids)):raise ValueError('Original component count differs')
        qcount=struct.unpack('<I',u.mem_read(0x03002a20,4))[0]
        if qcount!=len(ids):raise ValueError('Header DMA count differs')
        if bytes(u.mem_read(scratch-4,4))!=b'\xa5'*4 or bytes(u.mem_read(scratch+128*len(ids),4))!=b'\xa5'*4:raise ValueError('Header scratch boundary changed')
        canvas=[[0]*84 for _ in range(8)]
        for i,idx in enumerate(ids):
            source,dest,raw=decompressed[i]
            wantsrc=0x08000000+bank+struct.unpack_from('<I',rom,bank+4+idx*4)[0]
            if source!=wantsrc or dest!=scratch+i*128:raise ValueError('Typed header source/scratch linkage differs')
            dma=struct.unpack('<IIII',u.mem_read(0x03002820+i*16,16))
            if dma!=(dest,0x06010000+(196+4*i)*32,0x84000020,128):raise ValueError('Original DMA header extent differs')
            dx,dy,shape,palette,tileoff=struct.unpack('<bbBBI',u.mem_read(desc+4+i*8,8))
            if (dy,shape,palette,tileoff)!=(0,5,0,i*4):raise ValueError('Original 32x8 component descriptor differs')
            for t in range(4):
                pixels=[v for b in raw[t*32:(t+1)*32] for v in (b&15,b>>4)]
                for py in range(8):
                    for px in range(8):
                        z=pixels[py*8+px]
                        if z:canvas[py][dx+t*8+px]=z
            loads+=1
        expected=[[0]*84 for _ in range(8)]
        for start,word in [(0,'특기'),(20,text.split()[1])]:
            for ci,c in enumerate(word):
                for yy,row in enumerate(glyphs[c]):
                    for xx,pixel in enumerate(row):expected[yy][start+ci*8+xx]=4 if pixel=='#' else 0
                pixel_cases+=1
        if canvas!=expected:raise ValueError('Original composite does not render exact Korean header pixels')
        cases.append({'type':kind,'text':text,'resources':ids,'anchor':[anchor,0]})
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'header_cases':cases,'resource_load_cases':loads,'letter_pixel_cases':pixel_cases,'scope':'Original type dispatch, graphics shape-size lookup, relative bank getter, rounded scratch allocation, decompression dispatch and DMA queue. BIOS RLE interpreted with strict output bounds; isolated OBJ allocation and observed compositor boundary. Full GPU and input require runtime observation.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
