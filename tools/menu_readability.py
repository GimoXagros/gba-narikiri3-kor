"""Local bitmap contrast recipes; preserve native descriptors and palettes."""
import hashlib,json,struct
from pathlib import Path
import numpy as np
from gba_rle import unpack
from adopted_graphics import mgba_diagnostic
from packing_codecs import optimal_lz77
from verify_graphics_candidate_edges import decode_stream

ROOT=Path(__file__).resolve().parents[1]
sha=lambda x:hashlib.sha256(x).hexdigest()
SHAPES=((8,8),(16,16),(32,32),(64,64),(16,8),(32,8),(32,16),(64,32),(8,16),(8,32),(16,32),(32,64))

def decode_resource(base,at,n):
    if int.from_bytes(base[at+1:at+4],'little')!=n:raise ValueError('Readability declared decoded length')
    if base[at]==0x30:
        try:return unpack(base,at,len(base),n)
        except ValueError as e:
            if str(e)!='RLE run exceeds decoded extent':raise
            raw,end,_=mgba_diagnostic(base,at)
            if len(raw)!=n:raise ValueError('Readability inherited diagnostic extent')
            return raw,end
    if base[at]!=0x10:raise ValueError('Readability source codec')
    raw,used,_=decode_stream(base[at:]);return raw,at+used

def components(base,index):
    frame=struct.unpack_from('<I',base,0xdd26ec+4*index)[0]-0x08000000
    if struct.unpack_from('<I',base,frame)[0]!=1:raise ValueError('Readability native frame count')
    at=struct.unpack_from('<I',base,frame+4)[0]-0x08000000
    n=struct.unpack_from('<I',base,at)[0];blob=base[at:at+4+8*n]
    rows=[]
    for i in range(n):
        x,y,shape,pal,tile=struct.unpack_from('<bbBBI',blob,4+8*i)
        if shape>=12 or pal!=0:raise ValueError('Readability native shape/palette')
        w,h=SHAPES[shape];rows.append((x+32,y+8,w,h,tile))
    return at,blob,rows

def raster(raw,parts):
    pix=np.zeros((16,64),np.uint8);used=set()
    for dx,dy,w,h,tile in parts:
        for y in range(h):
            for x in range(w):
                at=(tile+(y//8)*(w//8)+x//8)*32+(y%8)*4+(x%8)//2
                if not(0<=at<len(raw) and 0<=dy+y<16 and 0<=dx+x<64):raise ValueError('Readability component bounds')
                key=(at,x%2)
                if key in used:raise ValueError('Readability duplicate component pixel')
                used.add(key);pix[dy+y,dx+x]=(raw[at]>>(4*(x%2)))&15
    if len(used)!=1024:raise ValueError('Readability incomplete component coverage')
    return pix

def inverse(raw,pix,parts):
    result=bytearray(raw)
    for dx,dy,w,h,tile in parts:
        for y in range(h):
            for x in range(w):
                at=(tile+(y//8)*(w//8)+x//8)*32+(y%8)*4+(x%8)//2;shift=4*(x%2)
                result[at]=(result[at]&~(15<<shift))|(int(pix[dy+y,dx+x])<<shift)
    return bytes(result)

def field_pixels(base,raw,index):
    at,blob,parts=components(base,index);old=raster(raw,parts);new=old.copy()
    ink=old==8;region=np.zeros_like(ink);region[2:14,8:56]=True;ink&=region
    if not ink.any():raise ValueError('Readability field foreground missing')
    for y,x in zip(*np.where(ink)):
        for yy in range(max(2,y-1),min(14,y+2)):
            for xx in range(max(8,x-1),min(56,x+2)):
                if not ink[yy,xx] and old[yy,xx] in (3,6):new[yy,xx]=1
    if not np.array_equal(old==8,new==8) or not np.array_equal(old[~region],new[~region]):raise ValueError('Readability protected foreground/decorations')
    result=inverse(raw,new,parts)
    if not np.array_equal(raster(result,parts),new):raise ValueError('Readability inverse component roundtrip')
    return result,dict(descriptor_offset=at,descriptor_sha256=sha(blob),foreground_pixels=int(ink.sum()),changed_pixels=int((old!=new).sum()),protected_pixels_outside_text_equal=True,foreground_mask_equal=True)

def info_pixels(raw):
    if len(raw)!=128:raise ValueError('Readability info extent')
    old=np.zeros((8,32),np.uint8)
    for k,v in enumerate(raw):
        y=(k%32)//4;x=(k//32)*8+(k%4)*2;old[y,x]=v&15;old[y,x+1]=v>>4
    if set(np.unique(old))-set((0,4)):raise ValueError('Readability info source colors')
    ink=old==4;new=old.copy()
    for y,x in zip(*np.where(ink)):
        new[max(0,y-1):min(8,y+2),max(0,x-1):min(32,x+2)]=4
    new[ink]=15
    if not np.array_equal(new==15,ink):raise ValueError('Readability info foreground shape')
    result=bytes(int(new[y,tx*8+x])|int(new[y,tx*8+x+1])<<4 for tx in range(4) for y in range(8) for x in range(0,8,2))
    return result,dict(foreground_pixels=int(ink.sum()),outline_pixels=int((new==4).sum()),foreground_mask_equal=True)

def readability_writes(base,normal32=False):
    source=json.loads((ROOT/'source/v13_fixes/menu_readability.json').read_text('utf8'))
    kind='normal32' if normal32 else 'rc16'
    if sha(base)!=source['baseline_sha256'][kind]:raise ValueError('Readability exact C4 applicability')
    writes=[];records=[]
    for row in source['resources']:
        bank=int(row['bank'],0);field=bank+4+4*row['index'];at=bank+struct.unpack_from('<I',base,field)[0]
        binding=row['bindings'][kind];end=int(binding['owned_end'],0)
        if at!=int(binding['source_start'],0) or sha(base[at:end])!=binding['owned_source_sha256']:raise ValueError('Readability exact owned slot '+row['label'])
        raw,used=decode_resource(base,at,row['decoded_bytes'])
        if used!=int(binding['old_consumed_end'],0) or sha(raw)!=row['old_raw_sha256']:raise ValueError('Readability source pixels '+row['label'])
        new,report=field_pixels(base,raw,row['index']) if row['kind']=='field' else info_pixels(raw)
        if row['kind']=='field' and report['descriptor_sha256']!=row['descriptor_sha256']:raise ValueError('Readability original descriptor differs')
        blob=optimal_lz77(new)
        if sha(new)!=row['new_raw_sha256'] or sha(blob)!=row['new_stream_sha256'] or len(blob)!=row['new_stream_bytes'] or at+len(blob)>end:raise ValueError('Readability regeneration/slot overflow '+row['label'])
        if decode_resource(blob,0,len(new))!=(new,len(blob)):raise ValueError('Readability final codec roundtrip')
        writes.append(dict(writer='local readability '+row['label'],offset=at,payload=blob,allowed_end=end,expected_sha256=sha(base[at:at+len(blob)])))
        records.append(dict(row,verification=report))
    return writes,dict(resources=records,palette_descriptor_consumer_code_unchanged=True,new_static_RAM_bytes=0,scope='Native field menu eight labels and shared skill setting/use bitmap headers; local contrast adaptation preserving Japanese gold button design.')
