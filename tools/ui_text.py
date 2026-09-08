"""Validated selection rules for the adopted small UI format strings."""
import re,struct
from text_codec import encode,decode

TOKEN=re.compile(r'%(?:[0-9]*[ds]|[01]g|[hl])')

def format_tokens(text):
    stripped=TOKEN.sub('',text)
    if '%' in stripped:raise ValueError('Unmodeled UI format token')
    return [t for t in TOKEN.findall(text) if t!='%h']

def selected_ui(profile,catalog,legacy,glyphs):
    if profile['schema']!=1 or catalog['schema']!=1 or catalog['policy']!='development_only_needs_review':raise ValueError('Invalid UI catalog policy')
    rows={r['id']:r for r in catalog['records']}
    if len(rows)!=len(catalog['records']) or set(rows)!={p['id'] for p in profile['records']}:raise ValueError('UI selection identities differ')
    result=[]
    for p in profile['records']:
        text=rows[p['id']]['text'];off=int(p['pointer_offset'],16);ptr=int(p['original_pointer'],16);pc=int(p['call_address'],16)-0x08000000
        if struct.unpack_from('<I',legacy,off)[0]!=ptr:raise ValueError('UI literal pointer differs')
        raw=bytes.fromhex(p['original_raw']);start=ptr-0x08000000
        if legacy[start:start+len(raw)+1]!=raw+b'\0' or legacy[pc:pc+4]!=bytes.fromhex(p['call_bytes']):raise ValueError('UI source/caller differs')
        hi,lo=struct.unpack_from('<HH',legacy,pc)
        delta=((hi&0x7ff)<<12)|((lo&0x7ff)<<1)
        if delta&0x400000:delta-=0x800000
        if hi&0xf800!=0xf000 or lo&0xf800!=0xf800 or pc+0x08000004+delta!=int(p['consumer'],16):raise ValueError('UI caller is not the declared Thumb BL consumer')
        for guard in p.get('guards',[]):
            g=int(guard['offset'],0);value=bytes.fromhex(guard['hex'])
            if legacy[g:g+len(value)]!=value:raise ValueError('UI table loop/anchor differs')
        if format_tokens(decode(raw))!=format_tokens(text):raise ValueError('UI variable format/order changed')
        if '%h' in text:raise ValueError('Selected Korean UI does not need kana mode switches')
        if any(not ('\uac00'<=c<='\ud7a3' or 0x20<=ord(c)<=0x7e or c=='\n') for c in text):raise ValueError('Unsupported UI glyph/control')
        if text.count('\n')!=decode(raw).count('\n') or text.endswith('\n')!=decode(raw).endswith('\n'):raise ValueError('UI newline structure changed')
        if any('\uac00'<=c<='\ud7a3' and c not in glyphs for c in text):raise ValueError('Missing UI Hangul glyph')
        # Independent caller constraints: name editor has five slots; this
        # heading is also checked against the selected actor-name repertoire.
        worst=text.replace('%l','').replace('%0g','A').replace('%1g','B').replace('%s','가'*5).replace('%3d','19884').replace('%1d','9').replace('%2d','59')
        if max(map(len,worst.split('\n')))>p['selected_max_cells']:raise ValueError('UI exceeds selected caller width')
        if p['id']=='save-place-label' and len(text)!=8:raise ValueError('Location start would move')
        if 'exact_cells' in p and len(text)!=p['exact_cells']:raise ValueError('Adjacent setting position would move')
        for sample in p.get('format_samples',[]):
            sample_text=text.replace('%l','')%tuple(sample)
            if max(map(len,sample_text.split('\n')))>p['selected_max_cells']:raise ValueError('UI numeric boundary exceeds selected window')
        result.append((p['id'],off,encode(text)+b'\0'))
    return result
