"""Typed clothing creation/result text and its local visible-width helper."""
import hashlib,json,struct
from pathlib import Path
from text_codec import encode
ROOT=Path(__file__).resolve().parents[1]


def install(legacy,extension,code):
    profile=json.loads((ROOT/'source/clothing_result_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/clothing_results.json').read_text(encoding='utf-8'))
    if catalog['policy']!='development_only_needs_review':raise ValueError('Clothing review policy changed')
    if not len(code)<=0x100 or extension[0x900:0xa00]!=b'\xff'*0x100:raise ValueError('Clothing width code allocation collision')
    if extension[0xe0000:0xe1000]!=b'\xff'*0x1000:raise ValueError('Clothing text allocation collision')
    for g in profile['guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if legacy[off:off+len(raw)]!=raw:raise ValueError('Clothing source consumer differs')
    extension[0x900:0x900+len(code)]=code
    writes=[(0xd42a8,bytes.fromhex('004b1847')+struct.pack('<I',0x09000901),'Clothing result: count selected Hangul as one visible cell')]
    rows={r['id']:r for r in catalog['records']};cursor=0xe0000
    if set(rows)!={r['id'] for r in profile['records']}:raise ValueError('Clothing selected identities differ')
    for row in profile['records']:
        at=int(row['pointer_offset'],0);ptr=struct.unpack_from('<I',legacy,at)[0]-0x08000000;original=legacy[ptr:legacy.index(0,ptr)+1]
        if hashlib.sha256(original).hexdigest()!=row['original_sha256']:raise ValueError('Clothing text source differs')
        text=rows[row['id']]['text'];raw=encode(text)+b'\0'
        if any(ord(c)<32 for c in text):raise ValueError('Unmodeled clothing control')
        if row['id']=='creation':
            if not text.startswith('%s') or '%' in text[2:] or len(text[2:])!=12:raise ValueError('Creation name/order or original suffix width changed')
        elif row['id'] in ('increase','decrease'):
            if text.count('%s')!=1 or text.count('%d')!=1 or '%' in text.replace('%s','').replace('%d','') or text.index('%s')>text.index('%d'):raise ValueError('Clothing delta argument order changed')
            if len(encode(text%('공격력',128)))+1>32:raise ValueError('Clothing result exceeds original stack buffer')
        elif '%' in text or len(text)>3:raise ValueError('Clothing statistic name exceeds selected width')
        extension[cursor:cursor+len(raw)]=raw
        writes.append((at,struct.pack('<I',0x09000000+cursor),'clothing-result-'+row['id']));cursor+=len(raw)
    if cursor>0xe1000:raise ValueError('Clothing text allocation overflow')
    return writes,{'selected_fields':len(rows),'code_size':len(code),'text_start':'0x10e0000','text_end':hex(0x1000000+cursor),'scope':'Creation format and stat-change formats/labels only; actor/item identity and all signed stat values remain original.'}
