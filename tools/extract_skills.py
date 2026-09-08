"""Extract the fixed skill table selected by 08006E3C / 08006E68.

390 records at 08741DDC, stride 20; this is a table population, not a
claim that every record is reachable or that all game text is covered.
Raw source data is written only to the ignored analysis directory.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from text_codec import decode
from build_visibility_poc import J, K, sha

BASE=0x741ddc
COUNT=390

def extract(j, k):
    if sha(j)!=J or sha(k)!=K: raise ValueError('Unsupported source revision')
    rows=[]
    for i in range(COUNT):
        o=BASE+i*20
        fields=struct.unpack_from('<5I',j,o)
        if k[o:o+20]!=j[o:o+20]: raise ValueError('Unexpected changed skill record')
        row={'id':f'skill-{i:03d}','record_offset':hex(o),'attributes':list(fields[3:])}
        for name,ptr in zip(('compact','large','description'),fields):
            offset=ptr-0x08000000
            if not 0x1000c4<=offset<0x114000: raise ValueError('Skill pointer outside established text family')
            item={'offset':hex(offset)}
            for tag,rom,ko in [('j',j,False),('k11',k,True)]:
                end=rom.index(0,offset,offset+2048);raw=rom[offset:end]
                item[tag+'_raw']=raw.hex()
                try: item[tag+'_text']=decode(raw,ko)
                except (UnicodeError,ValueError) as e: item[tag+'_error']=str(e)
            row[name]=item
        rows.append(row)
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rows=extract(a.j.read_bytes(),a.legacy.read_bytes())
    a.out.write_text(json.dumps({'schema':1,'population':COUNT,'consumer':'08006E3C / 08006E68','records':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    for i in [164,176,285,286,287,324]:
        r=rows[i];print(r['id'],json.dumps({f:r[f] for f in ('compact','large')},ensure_ascii=False))

if __name__=='__main__':main()
