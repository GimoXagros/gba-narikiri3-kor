"""One-time draft preparation. Subsequent edits belong to translations/skills.json.

Preserves K1.1 wording except explicitly listed untranslated/corrupt names.
Every change remains reviewable. This script is not part of the ROM build.
"""
import argparse,json,unicodedata
from pathlib import Path
from extract_skills import extract
from text_codec import encode

FIXES={161:'박우',164:'인스펙트 아이',173:'카마이타치',176:'황왕천상익',
       186:'만주사화',189:'명공참상검',223:'사자전후',227:'상우열공격',266:'사자전후',
       285:'아련섬',286:'아련창파인',287:'아랑연도타',304:'진신연옥살',316:'작력부',
       324:'사후멸룡섬',332:'상월쌍섬',335:'취우쌍파참',338:'천상창파참'}
ND2_SHARED={161:'ARTE_117_FULL',164:'ARTE_120_FULL',173:'ARTE_129_FULL',176:'ARTE_132_FULL',
            186:'ARTE_142_FULL',189:'ARTE_145_FULL',223:'ARTE_179_FULL',227:'ARTE_183_FULL',266:'ARTE_222_FULL'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Draft exists; edit it explicitly instead of regenerating')
    rows=extract(a.j.read_bytes(),a.legacy.read_bytes());result=[]
    for i,r in enumerate(rows):
        large=FIXES.get(i,r['large'].get('k11_text'))
        if large is None:raise ValueError('Missing deliberate corruption repair')
        small=unicodedata.normalize('NFKC',large).replace('・','･').replace('−','-')
        if any(not ('\uac00'<=c<='\ud7a3' or 0x20<=ord(c)<=0x7e or c=='･') for c in small):raise ValueError(f'Untranslated name {i}: {small}')
        encode(small)
        result.append({'id':r['id'],'compact':small,'large_repair':large if i in FIXES else None,
            'basis':'Explicit untranslated/corrupt-name repair' if i in FIXES else 'Inherited K1.1 wording; width-only ASCII/space/punctuation representation',
            'reference':ND2_SHARED.get(i,'Original B3TJ glyph pixels + phonetic compact name' if i in FIXES else 'K1.1 same record'),
            'review':'pending','layout':'all_callers_pending'})
    a.out.write_text(json.dumps({'schema':1,'policy':'development_only_needs_review','population':390,'records':result},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'records':len(result),'explicit_repairs':len(FIXES),'max_compact_cells':max(len(r['compact']) for r in result)}))

if __name__=='__main__':main()
