"""Build fixed-size rendering optimizations from source. No private-file dependency."""
from pathlib import Path
import subprocess,struct,json,hashlib

def apply_performance(base:bytes,toolchain:Path,out:Path,source:Path|None=None):
    source=source or Path(__file__).resolve().parents[1]/'source/v13b/performance'
    toolchain=Path(toolchain);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    assert len(base)==0x1000000,'Requires16MiB input'
    def run(name,args):return subprocess.check_output([str(toolchain/('arm-none-eabi-'+name+'.exe')),*map(str,args)],text=True)
    def build(name,files,address=None,ld=None):
        d=out/name;d.mkdir();objects=[]
        for f in files:
            obj=d/(Path(f).stem+'.o');run('as',['-mcpu=arm7tdmi','-mthumb','-o',obj,source/f]);objects.append(obj)
        script=source/ld if ld else d/'layout.ld'
        if not ld:script.write_text(f'SECTIONS {{ . = {address}; .text : {{ *(.text) }} /DISCARD/ : {{ *(.ARM.attributes) }} }}')
        elf=d/'code.elf';run('ld',['-T',script,'-o',elf,*objects]);symbols={}
        for line in run('nm',['-n',elf]).splitlines():
            parts=line.split()
            if len(parts)==3:
                try:symbols[parts[2]]=int(parts[0],16)
                except ValueError:pass
        def section(n):
            p=d/(n+'.bin');run('objcopy',['-O','binary','-j','.'+n,elf,p]);return p.read_bytes()
        return section,symbols
    writes=[]
    def add(off,data,limit):
        assert len(data)<=limit,(hex(off),len(data),limit)
        writes.append(dict(offset=off,expected_hex=base[off:off+len(data)].hex(),payload_hex=data.hex()))
    f,sm=build('small',['row_cache.s','small_final_half.s','small_label.s'],0x08fbbf70);add(0xfbbf70,f('text'),1132)
    f,_=build('match',['fast_match.s'],0x08fbcf00);add(0xfbcf00,f('text'),256)
    f,_=build('pin',['fast_pin.s'],0x08fbd000);add(0xfbd000,f('text'),128)
    f,_=build('glyph',['fast_halfspace.s'],0x08fbcd6c);add(0xfbcd6c,f('text'),0x194)
    f,_=build('large',['large_halfspace.s'],ld='large_halfspace.ld')
    for n,a,size in [('support',0x1244,0x9c),('glyph',0x1338,0xdc),('print',0x14f4,0x14c)]:add(a,f(n),size)
    f,shared=build('shared',['shared_context.s'],0x08fbd180);add(0xfbd180,f('text'),192)
    f,generic=build('generic',['generic_guard.s'],0x08fbd240);add(0xfbd240,f('text'),0x114)
    for a,expected in [(0x4488,'f0b54f464646c0b4'),(0x4506,'18bc9846a146f0bc01bc'),(0xfc6b9c,'f0b58ab008910400')]:assert base[a:a+len(bytes.fromhex(expected))].hex()==expected,(hex(a),'unrecognized instruction hook')
    add(0x4488,bytes.fromhex('004b1847')+struct.pack('<I',shared['redraw_enter']|1),8)
    add(0x4506,bytes.fromhex('014b18470046')+struct.pack('<I',shared['redraw_exit']|1),10)
    # Cache entry overlays a compiled small-section range intentionally.
    add(0xfbbf70,bytes.fromhex('004b1847')+struct.pack('<I',shared['cache_context_enter']|1),8)
    add(0xfc6b9c,bytes.fromhex('004b1847')+struct.pack('<I',generic['generic_guard']|1),8)
    add(0xcae18,bytes.fromhex('004b1847')+struct.pack('<I',sm['small_item_name_hook']|1),8)
    rom=bytearray(base)
    for w in writes:rom[w['offset']:w['offset']+len(bytes.fromhex(w['payload_hex']))]=bytes.fromhex(w['payload_hex'])
    assert len(rom)==len(base)
    report=dict(input_sha256=hashlib.sha256(base).hexdigest(),output_sha256=hashlib.sha256(rom).hexdigest(),writes=writes,small_symbols=sm,shared_symbols=shared,generic_symbols=generic,stack_bytes=64,callback_whitelist=['080CADD1','080CD7D5'],claim='Build only; requires final candidate CPU and runtime checks')
    (out/'PERFORMANCE_BUILD.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return bytes(rom),report
