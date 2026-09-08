"""Selected music title fields and a special field-speaker getter literal."""
import hashlib,json,struct
from pathlib import Path
from text_codec import encode
ROOT=Path(__file__).resolve().parents[1]


def install(legacy,extension):
    p=json.loads((ROOT/'source/notice_text_profile.json').read_text(encoding='utf-8'))
    c=json.loads((ROOT/'translations/notices.json').read_text(encoding='utf-8'))
    if c['policy']!='development_only_needs_review' or len(c['records'])!=13:raise ValueError('Notice selection differs')
    if hashlib.sha256(legacy[0xd441bc:0xd4427c]).hexdigest()!=p['music_table_sha256']:raise ValueError('Original music table differs')
    for g in p['guards']:
        at=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if legacy[at:at+len(raw)]!=raw:raise ValueError('Notice consumer code differs')
    if extension[0x100000:0x101000]!=b'\xff'*0x1000:raise ValueError('Notice pool collision')
    cursor=0x100000;writes=[]
    for i,row in enumerate(c['records']):
        at=0xd441c8+i*16 if i<12 else 0xa5620
        if int(row['pointer_offset'],0)!=at:raise ValueError('Notice pointer identity/order differs')
        ptr=struct.unpack_from('<I',legacy,at)[0];off=ptr-0x08000000
        if ptr!=int(row['original_pointer'],0) or hashlib.sha256(legacy[off:legacy.index(0,off)+1]).hexdigest()!=row['original_sha256']:raise ValueError('Notice source differs')
        text=row['text']
        if not 1<=len(text)<=(19 if i<12 else 8) or any(not ('\uac00'<=ch<='\ud7a3' or ch in ' /0123456789') for ch in text):raise ValueError('Notice control/glyph or width differs')
        # Original 167B0 counts full-width spaces, but ignores ASCII spaces.
        # Use its established full-width blank glyph for centered titles.
        raw=encode(text.replace(' ','　') if i<12 else text)+b'\0'
        # The actual music object has +04..+2F for the centered string.
        if i<12 and ((19-len(text))//2)*2+len(raw)>44:raise ValueError('Centered music title exceeds original object buffer')
        extension[cursor:cursor+len(raw)]=raw
        writes.append((at,struct.pack('<I',0x09000000+cursor),row['id']));cursor+=len(raw)
    if cursor>0x101000:raise ValueError('Notice pool overflow')
    return writes,{'selected_fields':13,'music_titles':12,'field_speaker_literals':1,'text_start':'0x1100000','text_end':hex(0x1000000+cursor)}
