"""Apply the user's selected names to established static speaker identities."""
import argparse,json,struct
from pathlib import Path
from text_codec import decode
from build_visibility_poc import J,K,sha
p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--terms',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True);a=p.parse_args()
j=a.j.read_bytes();k=a.legacy.read_bytes()
if sha(j)!=J or sha(k)!=K:raise ValueError('Unsupported sources')
terms=json.loads(a.terms.read_text(encoding='utf-8'))['characters'];catalog=json.loads(a.catalog.read_text(encoding='utf-8'))
large=[None]*93;changes=[]
for i in range(93):
    if i in (43,44,49,50):continue
    ptr=struct.unpack_from('<I',j,0xec7944+i*20)[0]-0x08000000
    jp=decode(j[ptr:j.index(0,ptr)])
    try:old=decode(k[ptr:k.index(0,ptr)],True)
    except ValueError:old=None
    if jp in terms:
        chosen=terms[jp]
        if catalog['names'][i]!=chosen or old!=chosen:
            changes.append({'id':f'speaker-{i:03d}','japanese':jp,'previous_compact_selection':catalog['names'][i],'previous_large':old,'selected':chosen,'authority':'User-provided character list + explicit conflict resolution, 2026-09-09'})
        catalog['names'][i]=chosen
        if old!=chosen:large[i]=chosen
catalog['large_names']=large
catalog['wording_basis']='User selected character-list terminology where supplied; inherited K1.1 wording elsewhere. Player-save paths remain separate.'
catalog['terminology_sha256']=sha(a.terms.read_bytes())
a.catalog.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
a.ledger.write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'changed_identities':len(changes),'large_name_updates':sum(x is not None for x in large)}))
