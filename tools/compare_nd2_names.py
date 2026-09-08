"""Read-only cross-reference of exact JP names against the authorized ND2 v0.9b.

No ROM address or encoding from ND2 is used in ND3 output. Unmatched names
remain explicit; phonetic similarity is not an automatic identity match.
"""
import argparse,csv,json,hashlib,struct,unicodedata,re
from pathlib import Path
from text_codec import decode
from build_visibility_poc import J,sha

def key(text):return re.sub(r'\{BYTE:12\}|%h|[ \u3000]','',unicodedata.normalize('NFKC',text))
def text_at(rom,offset):
    ptr=struct.unpack_from('<I',rom,offset)[0]-0x08000000
    if not 0<=ptr<len(rom):raise ValueError('Pointer outside source')
    return decode(rom[ptr:rom.index(0,ptr)])

def main():
    p=argparse.ArgumentParser();p.add_argument('--nd2-j',type=Path,required=True);p.add_argument('--nd2-repo',type=Path,required=True);p.add_argument('--j',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    j2=a.nd2_j.read_bytes();j=a.j.read_bytes()
    if sha(j2)!='a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7' or sha(j)!=J:raise ValueError('Source mismatch')
    result={}
    for group,t2,s2,n2,t3,s3,n3,file in [('item',0x2b2cac,20,157,0x105758,24,123,'banked_item_names.tsv'),('monster',0x2bf4d4,52,165,0x1021ac,56,212,'banked_monster_names.tsv')]:
        terms={r['id']:r['text'] for r in csv.DictReader((a.nd2_repo/'translation'/file).open(encoding='utf-8'),delimiter='\t')}
        lookup={}
        for i in range(n2):
            identity=f'{group.upper()}_{i:03d}';jp=text_at(j2,t2+i*s2)
            value=(identity,terms[identity])
            k=key(jp)
            if k in lookup and lookup[k][1]!=value[1]:raise ValueError('Ambiguous ND2 term')
            lookup[k]=value
        rows=[]
        for i in range(n3):
            offset=t3+i*s3;jp=text_at(j,offset);found=lookup.get(key(jp))
            rows.append({'id':f'{group}-{i:03d}','japanese':jp,'nd2_reference':found[0] if found else None,'suggested':found[1] if found else None,'source_record_sha256':sha(j[offset:offset+s3])})
        result[group]=rows
        print(group,'exact matches',sum(r['suggested'] is not None for r in rows),'of',n3)
        for r in rows:
            if r['suggested'] is None:print(r['id'],r['japanese'])
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
