"""Four town-name sprite pairs; original lettering, palette and selector retained."""
import hashlib
import json
import struct
from pathlib import Path
from gba_rle import unpack, pack_literals

ROOT=Path(__file__).resolve().parents[1]
START,END=0x180000,0x182000

def source_canvas(rom,bank,number):
    pixels=[[0]*64 for _ in range(16)]
    for half,index in enumerate((58+number,73+number)):
        at=bank+struct.unpack_from('<I',rom,bank+4+index*4)[0]
        raw,_=unpack(rom,at,len(rom),256)
        for tile in range(8):
            for k,byte in enumerate(raw[tile*32:tile*32+32]):
                for nibble,value in enumerate((byte&15,byte>>4)):
                    x=half*32+(tile%4)*8+(2*k+nibble)%8
                    y=(tile//4)*8+(2*k+nibble)//8
                    pixels[y][x]=value
    return pixels

def tile_half(pixels,half):
    result=bytearray()
    for tile in range(8):
        for y in range(8):
            row=pixels[(tile//4)*8+y]
            for x in range(0,8,2):
                at=half*32+(tile%4)*8+x
                result.append(row[at]|row[at+1]<<4)
    return bytes(result)

def outlined(mask):
    h,w=len(mask),len(mask[0]);out=[[0]*w for _ in range(h)]
    points={(x,y) for y,row in enumerate(mask) for x,c in enumerate(row) if c=='#'}
    for x,y in points:
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                if not (0<=x+dx<w and 0<=y+dy<h):raise ValueError('Authored letter outline clips')
                out[y+dy][x+dx]=1
    for x,y in points:out[y][x]=2
    return out

def compose(legacy,profile,number):
    source=source_canvas(legacy,int(profile['bank'],0),number)
    result=[[0]*64 for _ in range(16)]
    def copy(x,start,width):
        for y in range(12):result[y][x:x+width]=source[y][start:start+width]
    def letter(x,name):
        pixels=outlined(profile['authored_masks'][name])
        for y,row in enumerate(pixels):result[y][x:x+len(row)]=row
    if number==0:
        copy(0,0,27);copy(31,27,28);width=59
        for y in range(12):
            if result[y][:27]+result[y][31:59] != source[y][:55]:
                raise ValueError('Research title lettering lost source pixels')
        if any(v for row in source[:12] for v in row[55:]):
            raise ValueError('Research source lettering exceeds established extent')
    elif number==3:copy(0,0,36);letter(40,'샵');width=50
    elif number==5:
        # Original glyphs occupy 0..38, not four uniform nine-pixel cells.
        # Keep every source pixel, including the final dang outline at x=38.
        copy(0,0,19);copy(23,19,20);width=43
        for y in range(12):
            if result[y][:19]+result[y][23:43] != source[y][:39]:
                raise ValueError('Restaurant title lettering lost source pixels')
        if any(v for row in source[:12] for v in row[39:]):
            raise ValueError('Restaurant source lettering exceeds established extent')
    elif number==6:
        letter(0,'래');copy(9,9,9);letter(18,'래');copy(27,27,9);copy(40,36,19);width=59
    else:raise ValueError('Unselected town title')
    # Same three-row embossed underline as K1.1, bounded by the new lettering.
    for y in (12,14):result[y][:width]=[1]*width
    result[13][:width]=[1]+[2]*(width-2)+[1]
    if any(z not in (0,1,2) for row in result for z in row):raise ValueError('Palette index drift')
    return result,width

def install(legacy,extension):
    profile=json.loads((ROOT/'source/town_label_profile.json').read_text('utf-8'))
    bank=int(profile['bank'],0)
    for guard in profile['guards']:
        at=int(guard['offset'],0);raw=bytes.fromhex(guard['hex'])
        if legacy[at:at+len(raw)]!=raw:raise ValueError('Town title consumer guard differs')
    if extension[START:END]!=b'\xff'*(END-START):raise ValueError('Town title pool collision')
    cursor=START;writes=[];records=[]
    for item in profile['labels']:
        number=item['number'];pixels,width=compose(legacy,profile,number)
        for half,resource in enumerate(item['resources']):
            index=resource['index'];at=int(resource['offset'],0)
            if bank+struct.unpack_from('<I',legacy,bank+4+4*index)[0]!=at:raise ValueError('Town source linkage differs')
            raw,end=unpack(legacy,at,len(legacy),256)
            if hashlib.sha256(legacy[at:end]).hexdigest()!=resource['sha256']:raise ValueError('Town source payload differs')
            # Verify an untouched decode/re-encode roundtrip before the edited pair.
            unchanged=tile_half(source_canvas(legacy,bank,number),half)
            if unchanged!=raw:raise ValueError('Original town tile roundtrip failed')
            packed=pack_literals(tile_half(pixels,half))
            if cursor+len(packed)>END:raise ValueError('Town title pool exceeds bound')
            extension[cursor:cursor+len(packed)]=packed
            writes.append((bank+4+4*index,struct.pack('<I',0x1000000+cursor-bank),'town label '+str(index)))
            cursor=(cursor+len(packed)+3)&~3
        records.append({'number':number,'text':item['text'],'underline_width':width})
    return writes,{'labels':records,'changed_resources':8,'extension_start':hex(0x1000000+START),
        'extension_end':hex(0x1000000+cursor),'scope':'Four town title pairs only. Original selector, two 32x16 sprite geometry, anchors, palette and all other bank assets remain unchanged.'}
