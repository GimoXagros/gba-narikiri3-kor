"""Guard and relocate the 32 approved non-dialogue pointer strings."""
import hashlib
import json
import re
import struct
from pathlib import Path

from text_codec import decode,encode
from prepare_review_ui import ROOT,source_string

TOKEN=re.compile(r'%[0-9]*[A-Za-z]')


def sha(data):return hashlib.sha256(data).hexdigest()


def validate(j,k):
    profile=json.loads((ROOT/'source/review_ui_profile.json').read_text('utf-8'))
    catalog=json.loads((ROOT/'translations/review_ui.json').read_text('utf-8'))
    if profile['schema']!=1 or catalog['schema']!=1 or catalog['policy']!='development_only_needs_review':
        raise ValueError('UI review schema or policy differs')
    if (sha(j),sha(k))!=(profile['japanese_rom_sha256'],profile['legacy_rom_sha256']):
        raise ValueError('UI review original ROM hashes differ')
    start,end=int(profile['extension_start'],0),int(profile['extension_end'],0)
    if (start,end)!=(0x141000,0x150000):raise ValueError('UI review allocation differs')
    fields=profile['fields'];texts={r['stable_id']:r['text'] for r in catalog['records']}
    if len(fields)!=34 or len(texts)!=34 or {r['stable_id'] for r in fields}!=set(texts):
        raise ValueError('UI review selection differs')
    for row in fields:
        identity=row['stable_id'];at=int(row['pointer_offset'],0);ptr=int(row['source_pointer'],0)
        if at%4 or at+4>len(j) or struct.unpack_from('<I',j,at)[0]!=ptr or struct.unpack_from('<I',k,at)[0]!=ptr:
            raise ValueError('UI field pointer differs: '+identity)
        jr,kr=source_string(j,ptr),source_string(k,ptr)
        if sha(jr)!=row['japanese_raw_sha256'] or sha(kr)!=row['legacy_raw_sha256'] or decode(jr)!=row['japanese'] or decode(kr,True)!=row['legacy']:
            raise ValueError('UI field original text differs: '+identity)
        text=texts[identity]
        if decode(encode(text),True)!=text:
            raise ValueError('UI field encoding round trip differs: '+identity)
        if TOKEN.findall(text)!=TOKEN.findall(row['legacy']):
            raise ValueError('UI field format token sequence differs: '+identity)
        if text.count('\n')!=row['legacy'].count('\n'):
            raise ValueError('UI field line structure differs: '+identity)
        lines=[TOKEN.sub('',line) for line in text.split('\n')]
        if any(len(line)>18 for line in lines):
            raise ValueError('UI field static line exceeds 18 cells: '+identity)
    return profile,catalog


def install(j,k,extension):
    profile,catalog=validate(j,k)
    start,end=int(profile['extension_start'],0),int(profile['extension_end'],0)
    if extension[start:end]!=b'\xff'*(end-start):raise ValueError('UI review pool collision')
    texts={r['stable_id']:r['text'] for r in catalog['records']}
    cursor=start;shared={};allocations=[];writes=[]
    for row in profile['fields']:
        raw=encode(texts[row['stable_id']])+b'\0'
        if raw not in shared:
            if cursor+len(raw)>end:raise ValueError('UI review pool exhausted')
            shared[raw]=0x09000000+cursor;allocations.append((cursor,raw))
            cursor=(cursor+len(raw)+3)&~3
        writes.append((int(row['pointer_offset'],0),struct.pack('<I',shared[raw]),row['stable_id']+' reviewed UI text'))
    for at,raw in allocations:extension[at:at+len(raw)]=raw
    return writes,{'selected_fields':len(writes),'unique_strings':len(allocations),
        'text_start':hex(0x1000000+start),'text_end':hex(0x1000000+cursor),
        'source_scope':profile['scope']}
