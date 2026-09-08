"""Build checks for independently established finite non-dialogue tables."""
import hashlib,struct
from text_codec import encode

def selections(profile,catalog,legacy,glyphs):
    if profile['schema']!=1 or catalog['schema']!=1 or catalog['policy']!='development_only_needs_review':raise ValueError('Invalid small table input policy')
    base=int(profile['rule_base'],16);size=profile['rule_count']*profile['rule_stride']
    if hashlib.sha256(legacy[base:base+size]).hexdigest()!=profile['rule_sha256']:raise ValueError('Team rule structure changed')
    guard=int(profile['rule_loop_guard_offset'],16)
    if legacy[guard:guard+4]!=bytes.fromhex(profile['rule_loop_guard_hex']):raise ValueError('Team rule iteration bound changed')
    translated={r['id']:r['text'] for r in catalog['records']}
    required={r['id'] for g in profile['groups'] for r in g['records']}
    if len(translated)!=len(catalog['records']) or set(translated)!=required:raise ValueError('Small table identity population differs')
    out=[]
    for group in profile['groups']:
        getter=int(group['consumer_getter'],16)-0x08000000;code=bytes.fromhex(group['getter_bytes'])
        if legacy[getter:getter+len(code)]!=code:raise ValueError('Small table getter changed')
        if len(group['records'])!=group['count']:raise ValueError('Small table count mismatch')
        for i,row in enumerate(group['records']):
            ptr_offset=int(row['pointer_offset'],16);ptr=int(row['source_pointer'],16);raw=bytes.fromhex(row['source_raw'])
            if ptr_offset!=int(group['base'],16)+i*group['stride'] or struct.unpack_from('<I',legacy,ptr_offset)[0]!=ptr:raise ValueError('Small table original pointer/order differs')
            start=ptr-0x08000000
            if legacy[start:start+len(raw)+1]!=raw+b'\0':raise ValueError('Small table source boundary differs')
            # All removed 0x12 codes only select kana forms in these raw
            # name strings; there are no formatter/event arguments here.
            if any(b<0x20 and b!=0x12 for b in raw) or b'%' in raw:raise ValueError('Unmodeled small table source control')
            text=translated[row['id']]
            if not text or len(text)>group['max_cells']:raise ValueError('Small table window width exceeded')
            if any(not (c in glyphs or 0x20<=ord(c)<=0x7e) for c in text) or '%' in text:raise ValueError('Unsupported small table glyph/control')
            encoded=encode(text)+b'\0'
            if len(encoded)>32:raise ValueError('Small table encoded scratch bound exceeded')
            out.append((row['id'],ptr_offset,encoded))
    return out
