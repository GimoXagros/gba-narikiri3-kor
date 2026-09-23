"""Guarded native title copyright and staff-roll insertion."""
import hashlib,json,struct
from pathlib import Path
from gba_rle import unpack,pack_literals
ROOT=Path(__file__).resolve().parents[1]
START,END=0x184000,0x188000
BANK=0x7b5888
TEXT='© 이노마타 무츠미 © 후지시마 코스케'
ADDED=['-KOREAN TRANSLATION-','JJAYAL','XAGROS','(SPECIAL THANKS)','SSOARA00','ARUMI','JOJO','AND YOU']

def pixels(raw):
    canvas=[[0]*224 for _ in range(32)]
    for left,width,first in ((0,64,0),(64,64,32),(128,64,64),(192,32,96)):
        for y in range(32):
            for x in range(width):
                at=(first+y//8*(width//8)+x//8)*32+y%8*4+x%8//2
                canvas[y][left+x]=(raw[at]>>(4*(x%2)))&15
    return canvas

def pack(canvas):
    raw=bytearray(3584)
    for left,width,first in ((0,64,0),(64,64,32),(128,64,64),(192,32,96)):
        for y in range(32):
            for x in range(width):
                at=(first+y//8*(width//8)+x//8)*32+y%8*4+x%8//2
                raw[at]|=canvas[y][left+x]<<(4*(x%2))
    return bytes(raw)

def title_bitmap(legacy):
    raw,_=unpack(legacy,0x7b7ca8,len(legacy),3584)
    canvas=pixels(raw)
    if pack(canvas)!=raw:raise ValueError('Title tile roundtrip differs')
    original=[row[:] for row in canvas]
    glyphs=json.loads((ROOT/'source/title_copyright_glyphs.json').read_text('utf-8'))['glyphs']
    ink=set();left=0
    for ch in TEXT:
        if ch==' ':left+=4;continue
        g=glyphs[ch]
        ink.update((left+x,y) for y,row in enumerate(g['rows']) for x,c in enumerate(row) if c=='#')
        left+=g['advance']
    start=(224-left)//2
    ink={(x+start,y+5) for x,y in ink}
    for y in range(18):canvas[y]=[0]*224
    # Original title palette: dark gray outer edge, white lettering.
    for x,y in ink:
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            if not(0<=x+dx<224 and 0<=y+dy<18):raise ValueError('Copyright clips')
            canvas[y+dy][x+dx]=1
    for x,y in ink:canvas[y][x]=5
    if canvas[18:]!=original[18:]:raise ValueError('English copyright changed')
    return pack(canvas)

def install(legacy,extension):
    if extension[START:END]!=b'\xff'*(END-START):raise ValueError('Title/staff pool collision')
    if struct.unpack_from('<I',legacy,BANK+32)[0]!=0x7b7ca8-BANK:raise ValueError('Title bank differs')
    if struct.unpack_from('<I',legacy,0xdaeb0)[0]!=0x08fa4ea4:raise ValueError('Staff reader differs')
    packed=pack_literals(title_bitmap(legacy));extension[START:START+len(packed)]=packed
    cursor=(START+len(packed)+3)&~3
    rows=list(struct.unpack_from('<262I',legacy,0xfa4ea4))
    if rows[-1]!=0 or rows[234]!=0x081c3410 or rows[239]!=0x081c3404:raise ValueError('Staff order differs')
    inserted=[0x081c3d80]*2
    for text in ADDED:
        raw=text.encode('ascii')+b'\0'
        inserted.append(0x09000000+cursor)
        extension[cursor:cursor+len(raw)]=raw;cursor+=len(raw)
    cursor=(cursor+3)&~3
    updated=rows[:235]+inserted+rows[235:]
    table=cursor;raw=struct.pack('<'+str(len(updated))+'I',*updated)
    if cursor+len(raw)>END:raise ValueError('Staff pool full')
    extension[cursor:cursor+len(raw)]=raw
    return [(BANK+32,struct.pack('<I',0x1000000+START-BANK),'title-copyright'),
            (0xdaeb0,struct.pack('<I',0x09000000+table),'staff-table')],{
        'title':TEXT,'original_staff_rows':261,'new_staff_rows':271,'inserted':ADDED,
        'original_rows_preserved':True,'english_copyright_preserved':True,
        'pool_start':hex(0x1000000+START),'pool_end':hex(0x1000000+cursor+len(raw))}
