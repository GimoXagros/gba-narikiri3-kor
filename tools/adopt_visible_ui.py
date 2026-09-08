"""One-time adoption of individually inspected UI literals; not a build scan."""
import hashlib,json,struct
from pathlib import Path
from text_codec import decode

ROOT=Path(__file__).resolve().parents[1]
SELECTIONS=[
    ('menu-team',0xcc0dc,'080CC070','%s 팀',9,'Main menu team heading, 9-cell window; player name at most five slots; actor repertoire checked separately'),
    ('main-team',0xd1cdc,'080D1C74',' %s 팀\n',10,'Main menu panel heading; preserve initial space and following newline'),
    ('detail-team',0xd2ab0,'080D2A1A','%s 팀',9,'Separate team detail heading; same name accessor 08007894'),
    ('save-place-label',0xd01e4,'080D01CA','저장 장소   ',8,'Save location label; keep location start at column +8'),
    ('save-town',0xd01fc,'080D0206','미나클 마을',13,'Town branch; preserve established K1.1 prose terminology'),
    ('save-time-single',0xd0274,'080D0268','플레이 시간  %3d:0%1d',22,'Save time, minute 0..9 branch; original numeric specifiers retained'),
    ('save-time-double',0xd028c,'080D0280','플레이 시간  %3d:%2d',22,'Save time, minute 10..59 branch; original numeric specifiers retained'),
]

def main():
    j=next(ROOT.glob('*[[]J[]]*.gba')).read_bytes()
    if hashlib.sha256(j).hexdigest()!='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394':raise ValueError('Wrong source')
    profile=[];translations=[]
    for identity,offset,call,text,width,basis in SELECTIONS:
        ptr=struct.unpack_from('<I',j,offset)[0];start=ptr-0x08000000
        raw=j[start:j.index(0,start)];pc=int(call,16)-0x08000000
        profile.append({'id':identity,'pointer_offset':hex(offset),'original_pointer':hex(ptr),'original_raw':raw.hex(),
                        'call_address':'0x'+call,'call_bytes':j[pc:pc+4].hex(),'consumer':'08001DA8',
                        'selected_max_cells':width,'basis':basis,'variable_kinds':['name'] if identity.endswith('-team') else ['hours','minutes'] if 'time-' in identity else []})
        translations.append({'id':identity,'text':text,'review':'pending','layout':'isolated_formatter_and_runtime_review_pending'})
    (ROOT/'source/ui_profile.json').write_text(json.dumps({'schema':1,'scope':'Seven individually established literal callers; not the complete UI population','records':profile},ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'translations/ui.json').write_text(json.dumps({'schema':1,'policy':'development_only_needs_review','records':translations},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
