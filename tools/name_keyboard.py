"""Typed keyboard display pages and input cells, never dialogue extraction."""
import hashlib,json,struct
from pathlib import Path
from text_codec import encode,hangul_map

ROOT=Path(__file__).resolve().parents[1]
CODE=0x800
CELLS=0xb0000
ROWS=0xb2000
HEADERS=0xb2400
STRINGS=0xb3000
END=0xc0000

def resources(legacy,profile,catalog):
    if profile['schema']!=1 or catalog['schema']!=1 or catalog['policy']!='development_only_needs_review':raise ValueError('Keyboard policy differs')
    if (profile['page_count'],profile['hangul_pages'],profile['rows_per_page'],profile['columns'],profile['slots'],profile['bytes_per_slot'])!=(30,27,6,15,5,4):raise ValueError('Keyboard geometry differs')
    for r in profile['regions']:
        start,end=int(r['start'],0),int(r['end'],0)
        if hashlib.sha256(legacy[start:end]).hexdigest()!=r['sha256']:raise ValueError('Keyboard source region differs: '+r['id'])
    for r in profile['guards']:
        start=int(r['offset'],0);raw=bytes.fromhex(r['hex'])
        if legacy[start:start+len(raw)]!=raw:raise ValueError('Keyboard source guard differs')
    chars=list(hangul_map().values())
    if len(chars)!=2350 or len(set(chars))!=2350:raise ValueError('Candidate repertoire differs')
    if catalog['blank_cells']!='not_selectable' or len(catalog['actions'])!=3:raise ValueError('Unmodeled keyboard actions')
    pages=[];headers=[]
    for p in range(27):
        cells=(chars[p*90:(p+1)*90]+[' ']*90)[:90]
        rows=[]
        for r in range(6):
            row=' '.join(''.join(cells[r*15+g*5:r*15+g*5+5]) for g in range(3))
            if r>=3:row+='  '+catalog['actions'][r-3]
            if r<5:row+='\n'
            rows.append(encode(row))
        pages.append(rows);headers.append(encode(catalog['hangul_header']%(p+1)))
    # Keep the candidate part of every original display row byte for byte.
    # Only the three anchored action labels change. Original input lookup
    # tables and kana voicing rules are not written by this builder.
    labels=['ｷﾘｶｴ','ﾓﾄﾞﾙ','ｹｯﾃｲ']
    for p,table in enumerate(profile['original_display_tables']):
        rows=[]
        for r in range(6):
            off=struct.unpack_from('<I',legacy,int(table,0)+r*4)[0]-0x08000000
            raw=legacy[off:legacy.index(0,off)]
            if r>=3:
                ending=labels[r-3].encode('cp932')+(b'\n' if r<5 else b'')
                if not raw.endswith(ending):raise ValueError('Original keyboard action suffix differs')
                prefix=raw[:-len(ending)]
                if prefix.endswith(b'%h'):prefix=prefix[:-2]
                raw=prefix+encode(catalog['actions'][r-3])+(b'\n' if r<5 else b'')
            rows.append(raw)
        pages.append(rows);headers.append(encode(catalog['other_headers'][p]))
    for raw in [r for page in pages for r in page]+headers:
        if b'\0' in raw or len(raw)>=255:raise ValueError('Keyboard formatter buffer exceeded')
    for h in [catalog['hangul_header']%1,*catalog['other_headers']]:
        if len(h)>18:raise ValueError('Keyboard header window exceeded')
    cells=b''.join(encode(c) for c in chars)+bytes(80*2)
    return cells,pages,headers

def install(legacy,extension,out,run):
    profile=json.loads((ROOT/'source/name_keyboard_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/name_keyboard.json').read_text(encoding='utf-8'))
    cells,pages,headers=resources(legacy,profile,catalog)
    run('as',['-mcpu=arm7tdmi','-mthumb',ROOT/'source/name_keyboard.s','-o',out/'name-keyboard.o'])
    run('ld',['-Ttext=0x09000800','-e','keyboard_draw',out/'name-keyboard.o','-o',out/'name-keyboard.elf'])
    run('objcopy',['-O','binary','--only-section=.text',out/'name-keyboard.elf',out/'name-keyboard.bin'])
    (out/'name-keyboard.disassembly.txt').write_text(run('objdump',['-d','-m','armv4t',out/'name-keyboard.elf']),encoding='utf-8')
    code=(out/'name-keyboard.bin').read_bytes()
    if len(code)>0x800:raise ValueError('Keyboard code/font overlap')
    def put(off,data):
        if extension[off:off+len(data)]!=b'\xff'*len(data):raise ValueError('Keyboard extension allocation overlap')
        extension[off:off+len(data)]=data
    put(CODE,code);put(CELLS,cells)
    cursor=STRINGS
    def string(raw):
        nonlocal cursor
        data=raw+b'\0';cursor=(cursor+3)&~3;ptr=0x09000000+cursor
        if cursor+len(data)>END:raise ValueError('Keyboard string budget exceeded')
        put(cursor,data);cursor+=len(data)
        return struct.pack('<I',ptr)
    put(ROWS,b''.join(string(r) for page in pages for r in page))
    header_ptrs=b''.join(string(h) for h in headers);put(HEADERS,header_ptrs)
    symbols={line.split()[-1]:int(line.split()[0],16)|1 for line in run('nm',['-g','--defined-only',out/'name-keyboard.elf']).splitlines()}
    writes=[(off,bytes.fromhex('004b1847')+struct.pack('<I',symbols[name]),reason) for off,name,reason in [(0xd63e0,'keyboard_draw','Typed keyboard page renderer'),(0xd6470,'keyboard_insert','Typed Hangul cell to original four-byte name slot')]]
    writes.extend([(0xd62c6,bytes.fromhex('1d28'),'Side action page bound 29'),(0xd62f4,bytes.fromhex('1d26'),'L wraps to page 29; B mask remains 2'),(0xd634e,bytes.fromhex('1d28'),'R page bound 29'),(0xd6084,header_ptrs[:4],'Initial Korean keyboard header')])
    return writes,{'hangul_candidates':2350,'pages':30,'blank_cells_rejected':80,'code_size':len(code),'string_end':hex(cursor)}
