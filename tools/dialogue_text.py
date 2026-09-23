"""Adopted opcode-0F dialogue corrections; no text obtained from build scans."""
import re,struct
from text_codec import encode,decode
from dialogue_tokens import controls,unsafe_expansion_sequences,validate_dialogue_formats
from dialogue_structure import source_records
from review_dialogue_layouts import approved as approved_layout

# ROM extension-relative byte ranges. No executable hook or game data moves.
DIALOGUE_POOLS={'original':(0x80000,0x90000),'review':(0x160000,0x180000)}

def selections(profile,catalog,j,legacy):
    if profile['schema']!=1 or catalog['schema']!=1 or catalog['policy']!='development_only_needs_review':raise ValueError('Invalid dialogue catalog')
    for guard in profile['consumer_guards']:
        off=int(guard['offset'],0);b=bytes.fromhex(guard['hex'])
        if j[off:off+len(b)]!=b or legacy[off:off+len(b)]!=b:raise ValueError('Dialogue VM/expander consumer differs')
    rows={r['id']:r for r in catalog['records']}
    if len(rows)!=len(catalog['records']) or set(rows)!={r['id'] for r in profile['records']}:raise ValueError('Dialogue identity mismatch')
    result=[]
    adopted={r['record_offset'] for r in source_records(j,legacy)}
    tokens=lambda b:[t for _,t in controls(b)]
    for row in profile['records']:
        off=int(row['record_offset'],0);record=bytes.fromhex(row['source_record']);ptr=struct.unpack_from('<I',record,4)[0];start=ptr-0x08000000
        if off not in adopted:raise ValueError('Correction is not a dialogue record in the indexed VM resource')
        if len(record)!=8 or struct.unpack_from('<H',record)[0] not in (15,37) or j[off:off+8]!=record or legacy[off:off+8]!=record:raise ValueError('Not an adopted dialogue record')
        for rom,key in [(j,'j_raw'),(legacy,'legacy_raw')]:
            raw=bytes.fromhex(row[key])
            if rom[start:start+len(raw)+1]!=raw+b'\0':raise ValueError('Dialogue source differs')
        raw=bytes.fromhex(row['legacy_raw']);new=encode(rows[row['id']]['text'])
        validate_dialogue_formats(new)
        token_ref=bytes.fromhex(row['j_raw']) if row.get('control_source')=='j' else raw
        line_ref=bytes.fromhex(row['j_raw']) if row.get('newline_source')=='j' else raw
        newline_expected=row.get('extra_newline_count',line_ref.count(b'\n'))
        if row.get('extra_newline_count') is not None and (not approved_layout(rows[row['id']].get('review_id'),rows[row['id']]['text']) or newline_expected!=new.count(b'\n')):
            raise ValueError('Unreviewed dialogue scroll exception')
        if tokens(new)!=tokens(token_ref) or new.count(b'\n')!=newline_expected:raise ValueError('Dialogue controls/name substitutions changed')
        if unsafe_expansion_sequences(new):raise ValueError('Multibyte trail would be interpreted as a name macro: '+row['id'])
        if len(new)+8*sum(t.startswith(b'@') for t in tokens(new))>=256:raise ValueError('Potential name expansion beyond original 256-byte allocation')
        result.append((row['id'],off+4,new+b'\0'))
    return result
