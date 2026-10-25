"""Apply adopted display changes to the source-built, hash-bound v1.3 base."""
import hashlib,json,struct,subprocess
from pathlib import Path
from build_release import apply_writes
from gba_rle import unpack
from intro_graphics_stage import optimal_rle
from packing_codecs import optimal_lz77
from verify_graphics_candidate_edges import decode_stream

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source/v13a'
BASE='d1d27b49dfeb6bbacb77b2112664efbb679f7f30a89f2cd17a1037d64fef1c4b'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda name:json.loads((SOURCE/name).read_text('utf8'))

def assemble(tc,out,names,address,entry,script=None):
    out.mkdir(parents=True,exist_ok=False)
    def run(tool,args):return subprocess.check_output([str(tc/('arm-none-eabi-'+tool+'.exe')),*map(str,args)])
    objects=[]
    for name in names:
        obj=out/(name+'.o');run('as',['-mcpu=arm7tdmi',SOURCE/name,'-o',obj]);objects.append(obj)
    elf=out/'code.elf'
    placement=['-T',SOURCE/script] if script else [f'-Ttext={hex(address)}']
    run('ld',[*placement,'-e',entry,*objects,'-o',elf])
    symbols={p[2]:int(p[0],16) for line in run('nm',['-n',elf]).decode().splitlines() if len(p:=line.split())>=3}
    def section(name):
        target=out/(name+'.bin');run('objcopy',['-O','binary','--only-section=.'+name,elf,target]);return target.read_bytes()
    return section,symbols

def build(base,tc,out):
    if len(base)!=16777216 or sha(base)!=BASE:raise ValueError('Exact source-built BASE16 required')
    writes=[]
    def add(label,at,data,end):
        writes.append(dict(writer=label,offset=at,allowed_end=end,expected_sha256=sha(base[at:at+len(data)]),payload=data))
    for row in read('graphics.json')['writes']:
        if row['kind'] in ('bios-rle30','bios-lz77'):
            decoded=bytes.fromhex(row['decoded_hex'])
            if sha(decoded)!=row['decoded_sha256']:raise ValueError('Graphic source mismatch')
            if row['kind']=='bios-rle30':
                data=optimal_rle(decoded)
                if unpack(data,0,len(data),len(decoded))!=(decoded,len(data)):raise ValueError('Graphic roundtrip')
            else:
                data=optimal_lz77(decoded);raw,used,_=decode_stream(data)
                if raw!=decoded or used!=len(data):raise ValueError('Graphic LZ77 roundtrip')
        elif row['kind']=='immediate':data=bytes.fromhex(row['payload_hex'])
        else:raise ValueError('Unknown graphic source kind')
        at=row['offset']
        if sha(data)!=row['payload_sha256'] or sha(base[at:at+len(data)])!=row['expected_sha256']:raise ValueError('Graphic identity')
        add(row['writer'],at,data,row['allowed_end'])
    profile=read('word_spaces.json')
    if len(set(profile['offsets']))!=profile['unique_spaces']:raise ValueError('Space population')
    for at in profile['offsets']:
        if base[at:at+2]!=b'\x81\x40':raise ValueError('Word-space source')
        add('reviewed dialogue word space',at,b'\x16\x01',at+2)
    at=0x1070cc;old=base[at:base.index(0,at)]
    if sha(old)!='b26333957810d64fd63001cdcc7c342cc55f97ac707a1ecb9feabf398850cfcd':raise ValueError('Item9 description identity')
    add('verified item9 description spaces',at,old.replace(b'\x81\x40',b'\x16\x01'),at+len(old))
    sections,symbols=assemble(tc,out/'large',['large_halfspace.s'],None,'halfspace_print','large_halfspace.ld')
    for name,at,end in [('support',0x1244,0x12e0),('glyph',0x1338,0x1414),('print',0x14f4,0x1640)]:
        add('large '+name,at,sections(name),end)
    for label,at,sym in [('cursor setter',0x1674,'halfspace_cursor_set'),('clear bridge',0x1058,'halfspace_clear_bridge')]:
        add(label,at,bytes.fromhex('004b1847')+struct.pack('<I',symbols[sym]|1),at+8)
    sections,small_symbols=assemble(tc,out/'small',['row_cache.s','small_final_half.s','small_label.s'],0x08fbbf70,'small_item_name_hook')
    small=sections('text')
    if len(small)!=1132 or sha(small)!='2d30b16a8ddaff466359a2fe75fa116804a5c553a0601def785073d87946ec2c':raise ValueError('Frozen inventory code differs')
    add('verified inventory compositor',0xfbbf70,small,0xfbc3dc)
    if base[0xcae18:0xcae20]!=bytes.fromhex('2168281c36f7c4ff'):raise ValueError('Inventory caller guard')
    add('inventory name caller only',0xcae18,bytes.fromhex('004b1847')+struct.pack('<I',small_symbols['small_item_name_hook']|1),0xcae20)
    # Boot and approved reflow are supplied by their independently reviewed source profiles.
    from v13a_boot import boot_writes
    for row in boot_writes(base,tc,out/'boot'):add(**row)
    result,ledger=apply_writes(base,writes)
    from v13a_reflow import apply_reflow
    result,reflow_ledger=apply_reflow(result)
    if len(result)!=16777216:raise ValueError('ROM growth forbidden')
    for row in read('bindings.json'):
        field=int(row['pointer_offset'],0);at=int(row['current_pointer'],0)-0x08000000
        if result[field:field+4]!=base[field:field+4] or result[at+row['bytes']]!=base[at+row['bytes']]:raise ValueError('Pointer/terminator moved '+row['binding_id'])
    for row in read('inventory_policy.json')['rows']:
        at=int(row['pointer'],0)-0x08000000;raw=bytes.fromhex(row['raw_hex'])
        if base[at:at+len(raw)]!=raw or result[at:at+len(raw)]!=raw:raise ValueError('Stored name changed')
    return result,dict(base_writes=ledger,reflow_stages=reflow_ledger)
