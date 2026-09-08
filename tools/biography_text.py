"""Typed 37-record character library; five text pointers and one character ID."""
import hashlib,json,struct
from pathlib import Path
from text_codec import encode
ROOT=Path(__file__).resolve().parents[1]
START=0xd0000
END=0xe0000

def install(legacy,extension):
    profile=json.loads((ROOT/'source/biography_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/biographies.json').read_text(encoding='utf-8'))
    if profile['count']!=37 or profile['stride']!=24 or catalog['policy']!='development_only_needs_review':raise ValueError('Library structure/policy differs')
    base=int(profile['table'],0)
    if hashlib.sha256(legacy[base:base+37*24]).hexdigest()!=profile['table_sha256']:raise ValueError('Library source table differs')
    for g in profile['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if legacy[off:off+len(raw)]!=raw:raise ValueError('Library consumer guard differs')
    if extension[START:END]!=b'\xff'*(END-START):raise ValueError('Library allocation collision')
    if [r['index'] for r in catalog['records']]!=list(range(37)):raise ValueError('Library identities differ')
    writes=[];cursor=START;linked={};fields=0
    for record in catalog['records']:
        i=record['index']
        if struct.unpack_from('<I',legacy,base+i*24+20)[0]!=record['character_id']:raise ValueError('Library character identity differs')
        for field in record['fields']:
            slot=field['slot'];text=field['text']
            if not 0<=slot<5 or '%' in text or '\n' in text or any(ord(c)<32 for c in text):raise ValueError('Unmodeled biography string/control')
            if len(text)>(10 if slot==0 else 36):raise ValueError('Library text exceeds selected window')
            at=base+i*24+slot*4;ptr=struct.unpack_from('<I',legacy,at)[0]-0x08000000
            original=legacy[ptr:legacy.index(0,ptr)+1]
            if hashlib.sha256(original).hexdigest()!=field['original_sha256']:raise ValueError('Library text source differs')
            raw=encode(text)+b'\0'
            if raw not in linked:
                linked[raw]=0x09000000+cursor;extension[cursor:cursor+len(raw)]=raw;cursor+=len(raw)
            writes.append((at,struct.pack('<I',linked[raw]),f'library-{i:02d} text field {slot}'))
            fields+=1
    if cursor>END:raise ValueError('Library allocation overflow')
    return writes,{'records':37,'compact_names':37,'selected_text_fields':fields,'extension_start':hex(0x1000000+START),'extension_end':hex(0x1000000+cursor)}
