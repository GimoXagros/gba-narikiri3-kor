"""Candidate catalog only: retain unresolved members, never build from scans."""
from pathlib import Path
import argparse,collections,json,struct
from text_codec import decode

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--k',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    j=a.j.read_bytes();k=a.k.read_bytes();refs=collections.defaultdict(list)
    for i in range(0,len(j)-3,4):
        v=struct.unpack_from('<I',j,i)[0]
        if 0x081000c4<=v<0x081c8000:refs[v-0x08000000].append(i)
    rows=[]
    for start,owners in sorted(refs.items()):
        end=j.find(b'\0',start,start+4096)
        if end<0 or end-start<2:continue
        raw=j[start:end]
        try:txt=decode(raw)
        except (ValueError,UnicodeError):continue
        if '{BYTE:' in txt:continue
        if not any('\u3040'<=c<='\u9fff' or '\uff61'<=c<='\uff9f' for c in txt):continue
        kend=k.find(b'\0',start,start+4096)
        kr=k[start:kend]
        try:ktxt=decode(kr,True)
        except (ValueError,UnicodeError):ktxt=None
        rows.append(dict(id=f'candidate-{len(rows):05d}',offset=f'{start:08X}',j_raw=raw.hex(),k_raw=kr.hex(),j_text=txt,k_text=ktxt,
            reference_candidates=[f'{v:08X}' for v in owners],changed=raw!=kr,consumer_state='unresolved'))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    unchanged=[r for r in rows if not r['changed']]
    print(json.dumps(dict(candidates=len(rows),unchanged=len(unchanged),decode_failures=sum(r['k_text'] is None for r in rows),scope='pointer candidates into 1000C4..1C8000; graphics and other regions unresolved'),ensure_ascii=False))
    for r in unchanged[:160]:print(r['offset'],repr(r['j_text']))

if __name__=='__main__':main()
