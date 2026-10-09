"""Source-derived field wording and separate departure-list frame ownership."""
import hashlib,json,struct
from pathlib import Path
import numpy as np
from gba_rle import unpack
from packing_codecs import optimal_lz77
from intro_graphics_stage import optimal_rle

ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def decode_rect(raw,width,height):
    pixels=np.zeros((height,width),np.uint8)
    for k,v in enumerate(raw):
        tile=k//32;y=(tile//(width//8))*8+(k%32)//4;x=(tile%(width//8))*8+(k%4)*2
        pixels[y,x]=v&15;pixels[y,x+1]=v>>4
    return pixels

def encode_rect(pixels):
    height,width=pixels.shape
    return bytes(int(pixels[ty*8+y,tx*8+x])|int(pixels[ty*8+y,tx*8+x+1])<<4 for ty in range(height//8) for tx in range(width//8) for y in range(8) for x in range(0,8,2))

def thumb_bl(source,target):
    delta=target-(source+4)
    if delta&1 or not -(1<<22)<=delta<(1<<22):raise ValueError('ARM7 Thumb BL range/alignment')
    return struct.pack('<HH',0xf000|((delta>>12)&0x7ff),0xf800|((delta>>1)&0x7ff))

def field_and_list(base,normal32=False):
    expected='beca7cb1b008224841e610e73de08cfb538238be017fac1ba8dc0689e63155be' if normal32 else '167323a79da8dddf64780b7ea706e44721c5cc647034300ee25239749547420c'
    if sha(base)!=expected:raise ValueError('Exact clean optimized applicability')
    profile=json.loads((ROOT/'source/costume_label_profile.json').read_text('utf-8'))
    if profile['korean_label']!='갈아입기':raise ValueError('Adopted field term differs')
    field=0xe72ee8;at=0xe72ee0+struct.unpack_from('<I',base,field)[0]
    raw,end=unpack(base,at,len(base),512)
    if at!=0xe73100 or end!=0xe73268:raise ValueError('Field original complete stream extent')
    pixels=np.concatenate([decode_rect(raw[256:],32,16),decode_rect(raw[:256],32,16)],axis=1)
    original=pixels.copy();pixels[2:14,8:56]=3
    atlas_at=0xf1d734+struct.unpack_from('<I',base,0xf1d738)[0]
    atlas=base[atlas_at:atlas_at+profile['new_atlas_bytes']]
    glyphs=[]
    for index,ch in enumerate(profile['korean_label']):
        counts={13:0,14:0}
        for y in range(12):
            for x in range(12):
                tx=index*12+x;ty=y+2;tid=profile['styled_tiles'][(ty//8)*6+tx//8]
                byte=atlas[tid*32+(ty%8)*4+(tx%8)//2];value=(byte>>(4*(tx%2)))&15
                if value in (13,14):pixels[ty,8+tx]={13:8,14:6}[value];counts[value]+=1
        if not all(counts.values()):raise ValueError('Field approved glyph missing')
        glyphs.append({'character':ch,'foreground':counts[13],'outline':counts[14]})
    keep=np.ones((16,64),bool);keep[2:14,8:56]=False
    if not np.array_equal(pixels[keep],original[keep]):raise ValueError('Button decorations changed')
    new=encode_rect(pixels[:,32:])+encode_rect(pixels[:,:32]);packed=optimal_lz77(new)
    if len(packed)>end-at:raise ValueError('Field generated VRAM-safe LZ overflow')
    enemy_at=0xe72ee0+struct.unpack_from('<I',base,0xe72ef4)[0]
    enemy_raw,enemy_end=unpack(base,enemy_at,len(base),512)
    if enemy_at!=0xe735f8 or enemy_end!=0xe73785:raise ValueError('Enemy list original complete stream extent')
    enemy_packed=optimal_lz77(enemy_raw)
    if len(enemy_packed)!=282:raise ValueError('Enemy list lossless VRAM-safe LZ extent')
    listframe=0xe73714;listtable=0x11a0000 if normal32 else 0xfce1a0
    # The list owns a new left/top anchored frame. Header DD221C stays exact.
    components=struct.pack('<I',3)+b''.join(struct.pack('<bbBBI',x,0,shape,0,tile) for x,shape,tile in [(0,6,0),(32,6,8),(64,1,16)])
    frame=struct.pack('<II',1,0x08000000+listframe+8)+components
    table=bytearray(base[0xdd221c:0xdd227c])
    for selector in [1,5,10,16]:struct.pack_into('<I',table,4*selector,0x08000000+listframe)
    if base[0xa7654]!=16 or base[0xa77a8:0xa77ac]!=struct.pack('<I',0x08dd221c):raise ValueError('Departure original allocation/table literal source identity')
    if base[listtable:listtable+96]!=(b'\xff' if normal32 else b'\0')*96:raise ValueError('Owned list table arena source differs')
    if listframe<enemy_at+len(enemy_packed) or listframe+len(frame)>enemy_end:raise ValueError('Enemy reencoded owned capacity overflow')
    writes=[]
    def add(label,at,data,limit):writes.append(dict(writer=label,offset=at,payload=data,allowed_end=limit,expected_sha256=sha(base[at:at+len(data)])))
    add('field approved town glyphs mapped to field palette',at,packed,end)
    add('enemy button lossless VRAM-safe compression',enemy_at,enemy_packed,enemy_end)
    add('enemy resource retired suffix list-only left top frame',listframe,frame,enemy_end)
    add('separate departure list frame table',listtable,bytes(table),listtable+96)
    add('departure list table literal',0xa77a8,struct.pack('<I',0x08000000+listtable),0xa77ac)
    add('departure list allocation twenty tiles',0xa7654,b'\x14',0xa7655)
    if base[0xaf990:0xaf994]!=thumb_bl(0x080af990,0x080dd44c):raise ValueError('Field original RLE-only loader BL source')
    add('field existing generic decompressor dispatch',0xaf990,thumb_bl(0x080af990,0x080033f4),0xaf994)
    report={'field_resource':1,'field_bank':hex(0xe72ee0),'wording':'갈아입기','decoded_bytes':len(new),'stored_bytes':len(packed),'raw_sha256':sha(new),'town_atlas_sha256':sha(atlas),'glyphs':glyphs,'enemy_lossless_resource':4,'enemy_raw_sha256':sha(enemy_raw),'enemy_original_stored_bytes':enemy_end-enemy_at,'enemy_stored_bytes':len(enemy_packed),'list_frame':hex(listframe),'list_table':hex(listtable),'list_table_entries':24,'wide_selectors':[1,5,10,16],'header_table_preserved':True,'allocation_tiles':20,'new_static_RAM_bytes':0,'slot_authority':'Existing repaired16 owned retired boot tail plus original enemy-button actual397-byte stream, losslessly reencoded282 bytes. Frame uses exact retired consumed stream suffix. Requires independent reference and runtime review.'}
    return writes,report

def strict_fields(base):
    from adopted_graphics import mgba_diagnostic
    source=json.loads((ROOT/'source/v13_fixes/strict_fields.json').read_text('utf-8'));writes=[];report=[]
    for row in source['resources']:
        at=int(row['resource_start'],0);end=int(row['original_declared_consumer_end'],0)
        if sha(base[at:end])!=row['expected_stream_sha256']:raise ValueError('Strict field inherited stream source guard')
        raw,used,last=mgba_diagnostic(base,at);packed=optimal_rle(raw)
        if used!=end or sha(raw)!=row['declared_pixels_sha256'] or sha(packed)!=row['strict_stream_sha256'] or len(packed)!=end-at:raise ValueError('Strict field identical declared pixels/extent')
        decoded,strict_end=unpack(packed,0,len(packed),512)
        if decoded!=raw or strict_end!=len(packed):raise ValueError('Strict field regenerated decoder contract')
        changes=[k for k in range(len(packed)) if packed[k]!=base[at+k]]
        if changes!=[int(row['changes'][0]['offset'],0)-at]:raise ValueError('Strict field scope exceeds single inherited flag')
        k=changes[0];writes.append(dict(writer='strict field final literal '+str(row['index']),offset=at+k,payload=packed[k:k+1],allowed_end=end,expected_sha256=sha(base[at+k:at+k+1])))
        report.append(dict(index=row['index'],source=[at,end],declared_pixels_sha256=sha(raw),strict_sha256=sha(packed),changed_offset=at+k))
    return writes,report

def styled_glyphs(rows,height,width,foreground,outline,outline_height=None):
    pixels=np.zeros((height,width),np.uint8);points=set()
    for glyph in rows:
        lines=glyph['foreground_rows'];w=glyph['width'];h=glyph['height'];dx=glyph['destination_x']
        if len(lines)!=h or any(len(line)!=w or set(line)-set('.#') for line in lines):raise ValueError('Editable glyph shape')
        mask=bytes(int(v=='#') for line in lines for v in line)
        expected=glyph.get('glyph_sha256',glyph.get('source_mask_sha256',glyph.get('foreground_sha256')))
        if sha(mask)!=expected:raise ValueError('Editable foreground mask hash')
        ink={(dx+x,y) for y,line in enumerate(lines) for x,v in enumerate(line) if v=='#'}
        if points&ink or any(not(0<=x<width and 0<=y<height) for x,y in ink):raise ValueError('Editable glyph overlap/bounds')
        points|=ink
    for x,y in points:
        for yy in range(max(0,y-1),min(outline_height or height,y+2)):
            for xx in range(max(0,x-1),min(width,x+2)):pixels[yy,xx]=outline
    for x,y in points:pixels[y,x]=foreground
    return pixels

def graphic_fixes(base,normal32=False):
    """Repack only exact retired streams; retain each original bank consumer."""
    directory=ROOT/'source/v13_fixes';maps=json.loads((directory/'maps.json').read_text('utf-8'));towns=json.loads((directory/'towns.json').read_text('utf-8'));info=json.loads((directory/'info.json').read_text('utf-8'))
    payloads={};rows={};sources={};writes=[];report=[]
    def record(key,row,raw,bank,codec):
        field=int(row['pointer_field'],0);at=(bank+struct.unpack_from('<I',base,field)[0])&0xffffffff
        declared=int.from_bytes(base[at+1:at+4],'little');old,end=unpack(base,at,len(base),declared)
        if sha(old)!=row['old_raw_sha256'] or sha(raw)!=row['new_raw_sha256']:raise ValueError('Original or generated pixels differ '+key)
        if not(normal32 and key=='info52') and (at!=int(row['source_start'],0) or base[field:field+4].hex()!=row['expected_pointer_hex']):raise ValueError('Original resource binding '+key)
        packed=optimal_rle(raw)
        if sha(packed)!=row['new_rle_sha256']:raise ValueError('Editable RLE regeneration differs '+key)
        payloads[key]=optimal_lz77(raw) if codec=='LZ77' else packed
        rows[key]=dict(row,bank=bank,codec=codec,raw_sha256=sha(raw));sources[key]=(at,end)
        # No other bank entry may alias an object that this stage retires.
        count={0x750a00:25,0x75f474:91,0xf1d734:111}[bank]
        aliases=[i for i in range(count) if (bank+struct.unpack_from('<I',base,bank+4+i*4)[0])&0xffffffff==at]
        if aliases!=[row['index']]:raise ValueError('Resource source is shared '+key)
    for row in maps['resources']:
        pix=styled_glyphs(row['glyph_sources'],16,64,6,1);raw=encode_rect(pix[:,:32])+encode_rect(pix[:,32:])
        record('map'+str(row['index']),row,raw,0x750a00,'LZ77' if row['index']!=20 else 'RLE')
    for unit in towns['units']:
        pix=styled_glyphs(unit['glyphs'],16,64,2,1,12);width=unit['underline_width']
        for y in (12,14):pix[y,:width]=1
        pix[13,:width]=[1]+[2]*(width-2)+[1]
        if pix.tolist()!=unit['pixel_rows'] or sha(pix.tobytes())!=unit['pixels_sha256']:raise ValueError('Town complete raster recipe')
        for half,row in enumerate(unit['payloads']):record('town'+str(row['index']),row,encode_rect(pix[:,half*32:half*32+32]),0x75f474,'RLE')
    for row in info['resources']:
        pix=styled_glyphs(row['glyphs'],row['height'],row['width'],15,4)
        if pix.tolist()!=row['pixel_rows']:raise ValueError('Info complete raster recipe')
        record('info'+str(row['index']),row,encode_rect(pix),0xf1d734,'RLE' if row['index']==53 else 'LZ77')
    # Three whole retired objects exchange owners; info53 uses map6's exact
    # consumed suffix after VRAM-safe LZ. No inter-object alignment gap is owned.
    targets={key:(key,0) for key in rows}
    targets.update(map12=('map11',0),map11=('town65',0),town65=('map12',0),info53=('map6',(len(payloads['map6'])+3)&~3))
    used=[]
    for key,row in rows.items():
        owner,delta=targets[key];start,owner_end=sources[owner];target=start+delta;blob=payloads[key];end=target+len(blob)
        if target%4 or end>owner_end or any(target<b and end>a for a,b in used):raise ValueError('Exact retired stream packing bound '+key)
        used.append((target,end));field=int(row['pointer_field'],0)
        writes.append(dict(writer=key+' editable glyph raster '+row['codec'],offset=target,payload=blob,allowed_end=owner_end,expected_sha256=sha(base[target:end])))
        source_at,source_end=sources[key]
        if target!=source_at:
            writes.append(dict(writer=key+' original consumer bank binding',offset=field,payload=struct.pack('<I',(target-row['bank'])&0xffffffff),allowed_end=field+4,expected_sha256=sha(base[field:field+4])))
        report.append(dict(resource=key,index=row['index'],text=row.get('expected_korean',row.get('text')),codec=row['codec'],source=[source_at,source_end],target=[target,end],owner_resource=owner,owner=[start,owner_end],pointer_field=field,decoded_sha256=row['raw_sha256'],payload_sha256=sha(blob),decoded_bytes=int.from_bytes(blob[1:4],'little')))
    return writes,{'resources':report,'shared_info_resources_unchanged':[49,51,54,55,56,84,85,103],'logical_physical_binding':'51/54 retain original pixels; auxiliary52 and53 repair shared info groups.102 changes order wording;103 stays exact context member.','consumer_code_preserved':True,'new_persistent_RAM_bytes':0}

def final_fixes(base,normal32=False):
    writes,field=field_and_list(base,normal32);strict,strict_report=strict_fields(base);graphics,graphics_report=graphic_fixes(base,normal32)
    speaker,speaker_report=dynamic_speaker_prefix(base)
    return writes+strict+graphics+speaker,dict(field_list=field,strict_fields=strict_report,graphics=graphics_report,dynamic_speaker_prefix=speaker_report)

def dynamic_speaker_prefix(base):
    from text_codec import encode
    row=json.loads((ROOT/'source/v13_fixes/dynamic_speaker_prefix.json').read_text('utf-8'))
    if sha((ROOT/row['encoder']).read_bytes())!=row['encoder_sha256']:raise ValueError('Dynamic speaker encoder source differs')
    at=int(row['offset'],0);old=bytes.fromhex(row['expected_old_hex']);new=encode(row['text'])
    if len(old)!=4 or len(new)!=4 or new.hex()!=row['encoded_hex'] or base[at:at+4]!=old:raise ValueError('Dynamic speaker exact prefix/source/length guard')
    if row['speaker_ids']!=[49,50] or row['dynamic_name_copy_bytes']!=19 or row['buffer_spacing_bytes']!=24:raise ValueError('Dynamic speaker original copy contract')
    write=dict(writer='dynamic other-world speaker49/50 prefix '+row['text'],offset=at,payload=new,allowed_end=at+4,expected_sha256=sha(old))
    return [write],dict(offset=at,text=row['text'],encoded_hex=new.hex(),encoded_bytes=len(new),speaker_ids=row['speaker_ids'],dynamic_name_copy_bytes=19,buffer_spacing_bytes=24,code_pointers_dynamic_name_save_format_preserved=True,preserve_duplicate_offset=row['preserve_duplicate_offset'])
