"""Explicit 44 selected dungeon-label pointers used by the save summary."""
import hashlib,json,struct
from pathlib import Path
from text_codec import encode
ROOT=Path(__file__).resolve().parents[1]


def install(legacy,extension):
    p=json.loads((ROOT/'source/save_place_profile.json').read_text(encoding='utf-8'))
    c=json.loads((ROOT/'translations/save_places.json').read_text(encoding='utf-8'))
    base=int(p['table'],0)
    if len(c['records'])!=44 or c['policy']!='development_only_needs_review':raise ValueError('Save place selection changed')
    if hashlib.sha256(legacy[base:base+45*4]).hexdigest()!=p['source_table_and_test_sha256']:raise ValueError('Save place table/test boundary differs')
    for g in p['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if legacy[off:off+len(raw)]!=raw:raise ValueError('Save place code differs')
    if extension[0xf0000:0xf1000]!=b'\xff'*0x1000:raise ValueError('Save place allocation collision')
    writes=[];linked={};cursor=0xf0000
    for i,row in enumerate(c['records']):
        if row['index']!=i:raise ValueError('Save place identity/order differs')
        text=row['text'];ptr=struct.unpack_from('<I',legacy,base+4*i)[0]-0x08000000;raw=legacy[ptr:legacy.index(0,ptr)+1]
        if hashlib.sha256(raw).hexdigest()!=row['original_sha256']:raise ValueError('Save place source text differs')
        if not 1<=len(text)<=14 or '%' in text or any(ord(ch)<32 for ch in text):raise ValueError('Save place exceeds 22-cell window after 8-cell label')
        encoded=encode(text)+b'\0'
        if encoded not in linked:
            linked[encoded]=0x09000000+cursor;extension[cursor:cursor+len(encoded)]=encoded;cursor+=len(encoded)
        writes.append((base+i*4,struct.pack('<I',linked[encoded]),f'save-place-{i:02d}'))
    if cursor>0xf1000:raise ValueError('Save place allocation overflow')
    return writes,{'selected_fields':44,'test_slot_preserved':True,'text_start':'0x10f0000','text_end':hex(0x1000000+cursor)}
