"""Run emitted candidate pages, actual input/commit/delete and page controls."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from text_codec import encode,hangul_map
from verify_small_consumer import Fixture
from name_keyboard import resources,ROWS,HEADERS,CELLS,ROOT

CTX=0x02002000
GLOBAL=0x02004000
SENTINEL=0x0203fff0

class KeyboardFixture(Fixture):
    def __init__(self,rom,mode):
        super().__init__(rom,mode)
        self.uc.mem_write(0x02003380,struct.pack('<I',GLOBAL))
        for off,x,y,w,h in [(0x640,2,4,25,6),(0x648,2,1,8,1),(0x650,1,17,18,1)]:
            self.run(0x080016e8,GLOBAL+off,x,y,w,stack=h)
    def run(self,pc,r0=0,r1=0,r2=0,r3=0,stack=0,end=SENTINEL):
        u=self.uc
        for reg,val in [(UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_R2,r2),(UC_ARM_REG_R3,r3),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,SENTINEL|1)]:u.reg_write(reg,val)
        u.mem_write(0x03007e00,struct.pack('<I',stack))
        u.emu_start(pc|1,end,count=30000000)
        if u.reg_read(UC_ARM_REG_PC)!=end or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError(f'Keyboard CPU return mismatch at {pc:08X}')
    def name(self,text):
        self.uc.mem_write(0x02001000,encode(text)+b'\0')
        self.uc.mem_write(CTX,bytes(32))
        self.run(0x080d6754,CTX,0x02001000)
    def commit(self):
        self.uc.mem_write(0x02002800,b'\xa5'*32)
        self.run(0x080d66a8,CTX,0x02002800)
        data=bytes(self.uc.mem_read(0x02002800,32));end=data.index(0)
        if data[end+1:]!=b'\xa5'*(31-end):raise ValueError('Keyboard commit overrun')
        return data[:end]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();legacy=a.legacy.read_bytes()
    profile=json.loads((ROOT/'source/name_keyboard_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/name_keyboard.json').read_text(encoding='utf-8'))
    cells,pages,headers=resources(legacy,profile,catalog)
    if rom[0x1000000+CELLS:0x1000000+CELLS+len(cells)]!=cells:raise ValueError('Candidate cell bytes differ')
    for offset,values in [(ROWS,[r for page in pages for r in page]),(HEADERS,headers)]:
        for i,want in enumerate(values):
            ptr=struct.unpack_from('<I',rom,0x1000000+offset+i*4)[0]-0x08000000
            if not 0x10b3000<=ptr<0x10c0000 or rom[ptr:rom.index(0,ptr)]!=want:raise ValueError('Typed display pointer differs')
    allowed=set()
    for off,size in [(0xd63e0,8),(0xd6470,8),(0xd62c6,2),(0xd62f4,2),(0xd634e,2),(0xd6084,4),(0xd6754,8)]:allowed.update(range(off,off+size))
    for r in profile['regions']:
        s,e=int(r['start'],0),int(r['end'],0)
        if any(rom[i]!=legacy[i] for i in range(s,e) if i not in allowed):raise ValueError('Undeclared keyboard code/data write')
    glyphs=json.loads((ROOT/'fonts/dalmoori-wansung.json').read_text(encoding='utf-8'));chars=list(hangul_map().values())
    def glyph(f,c,x,y):
        nibbles=[n for b in f.tile(x,y) for n in (b&15,b>>4)]
        want=[15 if v=='#' else f.bg for row in glyphs[c] for v in row]
        if nibbles!=want:raise ValueError(f'Keyboard glyph mismatch: {c} at {x},{y}')
    drawn=inserted=legacy_cases=rejected=cycles=0;maximum=0
    for mode in (0,1):
        f=KeyboardFixture(rom,mode);u=f.uc;old=KeyboardFixture(legacy,mode)
        # Original 16E8/17A0 place mode 0 text one row below mode 1.
        line_offset=1-mode
        f.name('훌리오캐로')
        # Every page is drawn successively without resetting the atlas or map.
        # This exercises old-page clearing, name pinning and cache reuse.
        for page in list(range(30))+list(reversed(range(30))):
            f.run(0x080d63e0,page)
            for i,c in enumerate('훌리오캐로'):glyph(f,c,2+i,1+line_offset)
            if page<27:
                for i,c in enumerate(chars[page*90:(page+1)*90]):
                    glyph(f,c,2+i%15+(i%15)//5,4+line_offset+2*(i//15));drawn+=1
            else:
                original_mode=[2,0,1][page-27]
                old.run(0x080d63e0,original_mode)
                for y in range(4,16):
                    for x in range(2,19):
                        if f.tile(x,y)!=old.tile(x,y):raise ValueError('Original candidate pixels changed')
            for r,action in enumerate(catalog['actions']):
                for i,c in enumerate(action):glyph(f,c,21+i,10+line_offset+r*2)
            header=(catalog['hangul_header']%(page+1)) if page<27 else catalog['other_headers'][page-27]
            for i,c in enumerate(header):
                if c in glyphs:glyph(f,c,1+i,17+line_offset)
            indices={int.from_bytes(u.mem_read(0x03000060+i*2,2),'little')&1023 for i in range(1024)}
            slots=set(range(0x70,0xae))|set(range(0xb0,0xee));maximum=max(maximum,len(indices&slots))
        # Each input cell, each of the five storage positions, actual redraw,
        # commit, then delete. Guard adjacent context and output bytes.
        u.mem_write(0x03000060,bytes(2048))
        for index,c in enumerate(chars):
            page,cell=divmod(index,90);y,x=divmod(cell,15)
            for pos in range(5):
                prefix='가A나B'[:pos];f.name(prefix)
                before=bytes(u.mem_read(CTX,32));u.mem_write(CTX+20,bytes([page,pos,x,y]))
                f.run(0x080d6470,CTX)
                got=bytes(u.mem_read(CTX,32))
                if got[:pos*4]!=before[:pos*4] or got[pos*4:pos*4+4]!=encode(c)+b'\0\0' or got[21]!=pos+1 or got[24:]!=before[24:]:raise ValueError('Selected Hangul slot mismatch')
                if f.commit()!=encode(prefix+c):raise ValueError('Selected candidate commit differs')
                f.run(0x080d6630,CTX)
                if f.commit()!=encode(prefix):raise ValueError('Selected candidate deletion differs')
                inserted+=1
        # Every legacy candidate still produces the original slot bytes.
        for page,original_mode in [(27,2),(28,0),(29,1)]:
            for cell in range(90):
                y,x=divmod(cell,15)
                for fixture,pagenum in [(f,page),(old,original_mode)]:
                    fixture.uc.mem_write(CTX,bytes(32));fixture.uc.mem_write(CTX+20,bytes([pagenum,0,x,y]))
                    fixture.run(0x080d6470,CTX)
                if bytes(u.mem_read(CTX,20))!=bytes(old.uc.mem_read(CTX,20)):raise ValueError('Legacy input candidate changed')
                legacy_cases+=1
        invalid=[(26,0,i%15,i//15) for i in range(10,90)]+[(0,5,0,0),(30,0,0,0),(0,0,15,0),(0,0,0,6)]
        for state in invalid:
            u.mem_write(CTX,b'\xcc'*20+bytes(state)+b'\xa5'*8);before=bytes(u.mem_read(CTX,32))
            f.run(0x080d6470,CTX)
            if bytes(u.mem_read(CTX,32))!=before:raise ValueError('Invalid cell or full name modified context')
            rejected+=1
        # Execute original page dispatch. Only the unrelated sound callback is
        # substituted; input reading, masks, increments and wraps are original.
        def sound(uc,address,size,data):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        hook=u.hook_add(UC_HOOK_CODE,sound,begin=0x080dbecc,end=0x080dbecc)
        for page in range(30):
            for button,delta,x,y in [(1,1,15,3),(256,1,0,0),(512,-1,0,0)]:
                u.mem_write(CTX,b'\x00'*20+bytes([page,0,x,y])+b'\xa5'*8);before=bytearray(u.mem_read(CTX,32));before[20]=(page+delta)%30
                u.mem_write(0x030033f8,struct.pack('<H',button));u.reg_write(UC_ARM_REG_R4,CTX);u.reg_write(UC_ARM_REG_R5,0)
                f.run(0x080d6282,end=0x080d6354)
                if bytes(u.mem_read(CTX,32))!=bytes(before):raise ValueError('Page cycle damaged name/cursor')
                cycles+=1
        f.name('가A나');u.mem_write(CTX+20,b'\x1d');u.mem_write(0x030033f8,struct.pack('<H',2));u.reg_write(UC_ARM_REG_R4,CTX)
        f.run(0x080d6282,end=0x080d637c)
        if f.commit()!=encode('가A'):raise ValueError('B delete mask changed by L wrap constant')
        u.hook_del(hook)
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'successive_page_draws':120,'candidate_glyph_pixel_cases':drawn,'input_commit_delete_position_mode_cases':inserted,'legacy_input_cells_both_modes':legacy_cases,'invalid_blank_or_full_context_cases':rejected,'original_page_control_cases':cycles,'maximum_observed_pinned_cache_slots':maximum,'scope':'Actual Thumb keyboard display/input/commit/delete, every candidate and storage position, both font modes, original page controls with sound callback substituted. PC normal input, saved custom names and full-game cache lifetime remain separate.'}
    a.out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
