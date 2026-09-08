"""Execute the actual Thumb string consumer in an isolated CPU fixture.

This is a CPU/renderer contract check, not natural-play or full-game QA.
No fixture state is imported into the user's saves.
"""
import argparse,json,hashlib,struct
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from text_codec import encode,hangul_map

class Fixture:
    def __init__(self,rom,mode):
        self.uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for address,size in [(0x08000000,0x2000000),(0x02000000,0x40000),(0x03000000,0x8000),(0x06000000,0x18000),(0x04000000,0x1000),(0x05000000,0x1000)]:self.uc.mem_map(address,size)
        self.uc.mem_write(0x08000000,rom)
        self.uc.mem_write(0x03000050,struct.pack('<III',0x0600f800,0x0600c000,0))
        self.uc.mem_write(0x03001462,bytes([11 if mode else 0]))
        base=0xfdcc4 if mode else 0xfbcc4
        self.atlas=rom[base:base+0x2000]
        self.uc.mem_write(0x0600c000,self.atlas)
        self.bg=self.atlas[0x200]&15
    def draw(self,raw,clear=True,x=1,y=1,mark_mode=0):
        if clear:self.uc.mem_write(0x03000060,bytes(2048))
        self.uc.mem_write(0x02000000,bytes([1,1,31,30,x,y,mark_mode,13]))
        self.uc.mem_write(0x02001000,raw+b'\0')
        self.uc.reg_write(UC_ARM_REG_R0,0x02000000);self.uc.reg_write(UC_ARM_REG_R1,0x02001000)
        self.uc.reg_write(UC_ARM_REG_SP,0x03007e00);self.uc.reg_write(UC_ARM_REG_LR,0x0203fff1)
        self.uc.emu_start(0x08001a11,0x0203fff0,count=5000000)
        if self.uc.reg_read(UC_ARM_REG_PC)!=0x0203fff0:raise ValueError('Consumer did not return within instruction budget')
        if self.uc.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Stack imbalance')
    def tile(self,x,y):
        index=int.from_bytes(self.uc.mem_read(0x03000060+(y*32+x)*2,2),'little')&1023
        return bytes(self.uc.mem_read(0x0600c000+index*32,32))
    def pixels(self):return b''.join(self.tile(x,y) for y in range(32) for x in range(32))

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--glyphs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();legacy=a.legacy.read_bytes();glyphs=json.loads(a.glyphs.read_text(encoding='utf-8'))
    chars=list(hangul_map().values());checked=0;skill_cases=0;icon_cases=0
    fallback=[b'ABC 012!?', 'ｸﾚｽ ﾌﾞﾗｳﾝ ﾎﾜｲﾄ'.encode('cp932'),b'\x12'+ 'ｼｲﾅ ｽｽﾞ'.encode('cp932')+b'\x12', 'ﾊﾟﾋﾟﾌﾟﾍﾟﾎﾟ ｶﾞｷﾞｸﾞｹﾞｺﾞ'.encode('cp932')]
    for mode in (0,1):
        f=Fixture(rom,mode)
        for start in range(0,len(chars),20):
            chunk=chars[start:start+20];f.draw(encode(''.join(chunk)))
            for i,c in enumerate(chunk):
                nibbles=[v for b in f.tile(i+1,1) for v in (b&15,b>>4)]
                want=[15 if v=='#' else f.bg for row in glyphs[c] for v in row]
                if nibbles!=want:raise ValueError(f'Glyph mismatch {c}, mode {mode}, batch {start}')
                checked+=1
        # Compare original ASCII/kana/voicing behavior after the cache has
        # already been reused by every Hangul glyph, for all mark modes.
        original=Fixture(legacy,mode)
        for marks in (0,1,2):
            for raw in fallback:
                original.draw(raw,mark_mode=marks);f.draw(raw,mark_mode=marks)
                if original.pixels()!=f.pixels():raise ValueError(f'Fallback mismatch: {raw!r}, mode {mode}, marks {marks}')
        # Button graphics carry one raw index byte, including NUL and 10.
        # Verify the whole established 0..18 repertoire after cache reuse,
        # then keep it displayed while additional Hangul glyphs are drawn.
        icons=b''.join(b'\x13'+bytes([i]) for i in range(19))
        original.draw(icons,x=1,y=4)
        f.draw(encode('가나다라마바사아자차'));f.draw(icons,clear=False,x=1,y=4)
        expected_icons=[original.tile(x,4) for x in range(1,20)]
        if [f.tile(x,4) for x in range(1,20)]!=expected_icons:raise ValueError('Button graphics changed after cache reuse')
        icon_cases+=19
        f.draw(encode('쾌퀘후훤쾅벙땅뻘'),clear=False,x=1,y=6)
        if [f.tile(x,4) for x in range(1,20)]!=expected_icons:raise ValueError('Visible button graphics were overwritten by Hangul')
        icon_cases+=19
        # Drawing another label must leave an existing Korean label intact.
        f.draw(encode('브라운'));before=[f.tile(i,1) for i in (1,2,3)]
        f.draw(encode('화이트'),clear=False,x=10,y=1)
        if before!=[f.tile(i,1) for i in (1,2,3)]:raise ValueError('Live glyph evicted')
        # Fill every available slot with distinct bitmaps, then require visible
        # exhaustion without changing a single already displayed glyph.
        unique=[];seen=set()
        for c in chars:
            key=''.join(glyphs[c])
            if key not in seen:seen.add(key);unique.append(c)
        f.draw(encode(''.join(unique[:124])))
        coords=[(1+i%30,1+i//30) for i in range(124)]
        before=[f.tile(x,y) for x,y in coords]
        f.draw(encode(unique[124]),clear=False,x=20,y=10)
        if f.tile(20,10)!=f.atlas[0x2f*32:0x30*32]:raise ValueError('Exhaustion did not visibly signal ?')
        if before!=[f.tile(x,y) for x,y in coords]:raise ValueError('Exhaustion evicted visible glyphs')
        # Every linked skill name must pass the emitted pointer + original
        # consumer, including the formatter-free canonical Hangul bytes.
        if len(rom)>0x1000000 and int.from_bytes(rom[0x741ddc:0x741de0],'little')>=0x09000000:
            for i in range(390):
                ptr=struct.unpack_from('<I',rom,0x741ddc+i*20)[0]-0x08000000
                raw=rom[ptr:rom.index(0,ptr)]
                f.draw(raw);skill_cases+=1
    result=dict(status='PASS',claim='Isolated original Thumb consumer execution, not whole-game runtime',
        rom_sha256=hashlib.sha256(rom).hexdigest(),glyph_mode_cases=checked,kana_ascii_control_cases=24,live_label_cases=2,cache_capacity_and_exhaustion_cases=2,skill_consumer_cases=skill_cases,
        button_graphic_preservation_cases=icon_cases,
        limits=['Not all callers or font loaders covered','124-slot exhaustion is a verified development-only failure signal, not release behavior','No persistence or gameplay claim'])
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
