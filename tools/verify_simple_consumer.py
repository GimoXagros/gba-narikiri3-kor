"""Verify the distinct 08001DBC renderer without changing its spacing semantics."""
import argparse,json,hashlib
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode,hangul_map

class SimpleFixture(Fixture):
    def draw_simple(self,raw,clear=True,x=1,y=1):
        u=self.uc
        if clear:u.mem_write(0x03000060,bytes(2048))
        u.mem_write(0x02001000,raw+b'\0')
        for reg,val in [(UC_ARM_REG_R0,x),(UC_ARM_REG_R1,y),(UC_ARM_REG_R2,0x02001000),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,val)
        u.emu_start(0x08001dbd,0x0203fff0,count=5000000)
        if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Simple consumer return/stack mismatch')

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--glyphs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();legacy=a.legacy.read_bytes();glyphs=json.loads(a.glyphs.read_text(encoding='utf-8'));chars=list(hangul_map().values())
    count=0;fallbacks=0
    for mode in (0,1):
        f=SimpleFixture(rom,mode);original=SimpleFixture(legacy,mode)
        for start in range(0,len(chars),20):
            chunk=chars[start:start+20];f.draw_simple(encode(''.join(chunk)))
            for i,c in enumerate(chunk):
                got=[v for b in f.tile(i+1,1) for v in (b&15,b>>4)]
                want=[15 if v=='#' else f.bg for row in glyphs[c] for v in row]
                if got!=want:raise ValueError(f'Simple glyph mismatch {c} mode {mode}')
                count+=1
        for raw in [bytes(range(0x20,0x7f)),bytes(range(0xa1,0xe0)),b'\x12ABC\x12'+bytes([0xb6,0xde,0xbb,0xdf])]:
            f.draw_simple(raw);original.draw_simple(raw)
            if f.pixels()!=original.pixels():raise ValueError('Simple original spacing/pixels differ')
            fallbacks+=1
        f.draw(encode('훌리오'));before=[f.tile(i,1) for i in (1,2,3)]
        f.draw_simple(encode('캐로'),clear=False,x=10,y=1)
        if before!=[f.tile(i,1) for i in (1,2,3)]:raise ValueError('Cross-consumer live glyph overwritten')
    result={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'simple_glyph_mode_cases':count,'original_simple_spacing_cases':fallbacks,'cross_consumer_cases':2,'scope':'Actual original simple Thumb renderer; preserves separate voicing/spacing semantics; all game callers remain pending'}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
