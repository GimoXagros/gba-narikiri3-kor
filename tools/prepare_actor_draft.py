"""Bind user terms to the 96-record actor/costume table consumed by 080063FC.

Source-document costume numbers are deliberately not treated as game IDs.
"""
import argparse,json,struct,unicodedata
from pathlib import Path
from build_visibility_poc import J,K,sha
from text_codec import decode
p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--terms',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise ValueError('Draft exists; edit explicitly')
j=a.j.read_bytes();k=a.legacy.read_bytes()
if sha(j)!=J or sha(k)!=K:raise ValueError('Unsupported source')
terms=json.loads(a.terms.read_text(encoding='utf-8'));chosen=dict(terms['characters'])
chosen.update({r['j']:r['ko'] for r in terms['costumes'] if r['ko'] is not None})
aliases={'なりきり師':'なりきりし','剣士':'けんし','格闘家':'かくとうか','忍者':'ニンジャ','商人':'しょうにん','踊り子':'おどりこ','遊び人':'あそびにん','音楽家':'おんがくか','学者':'がくしゃ','手品師':'てじなし','盗賊':'とうぞく','和田かつ':'わだかつ','和田どん':'わだどん'}
rows=[]
for i in range(96):
    o=0x1000e4+i*72
    if j[o:o+8]!=k[o:o+8]:raise ValueError('Unexpected actor pointer change')
    ptr=struct.unpack_from('<I',j,o)[0]-0x08000000
    jp=decode(j[ptr:j.index(0,ptr)]);old=decode(k[ptr:k.index(0,ptr)],True)
    canonical=chosen.get(aliases.get(jp,jp))
    text=canonical or old
    small=text
    if i==94:text='적 훌리오';small='훌리오'
    elif i==95:text='적 캐로';small='캐로'
    small=unicodedata.normalize('NFKC',small).replace('・','･').replace('−','-')
    rows.append({'id':f'actor-{i:03d}','compact':small,'large':text if text!=old else None,
                 'wording_basis':'User selected character/costume term' if canonical else 'Inherited K1.1; enemy protagonist spelling follows user term' if i>=94 else 'Inherited K1.1',
                 'review':'layout_pending','source_record_sha256':sha(j[o:o+72])})
a.out.write_text(json.dumps({'schema':1,'policy':'development_only_needs_review','population':96,'terms_sha256':sha(a.terms.read_bytes()),'records':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'records':96,'large_name_changes':sum(r['large'] is not None for r in rows),'max_compact_cells':max(len(r['compact']) for r in rows)}))
