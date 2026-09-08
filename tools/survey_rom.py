"""Read-only initial survey. Candidates do not establish text consumers."""
from pathlib import Path
import argparse, collections, hashlib, json, re, struct, zlib

def identity(data):
    return dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                sha1=hashlib.sha1(data).hexdigest(), crc32=f'{zlib.crc32(data):08x}')

def ips_records(patch):
    if patch[:5] != b'PATCH': raise ValueError('Invalid IPS magic')
    pos=5; records=[]
    while patch[pos:pos+3] != b'EOF':
        if pos+5 > len(patch): raise ValueError('Truncated IPS record')
        offset=int.from_bytes(patch[pos:pos+3],'big')
        count=int.from_bytes(patch[pos+3:pos+5],'big'); pos+=5
        if count:
            data=patch[pos:pos+count]; pos+=count
            if len(data)!=count: raise ValueError('Truncated IPS payload')
        else:
            if pos+3 > len(patch): raise ValueError('Truncated IPS RLE')
            count=int.from_bytes(patch[pos:pos+2],'big')
            data=bytes([patch[pos+2]])*count; pos+=3
            if not count: raise ValueError('Empty RLE')
        records.append((offset,data))
    pos+=3
    if len(patch)-pos not in (0,3): raise ValueError('Invalid IPS trailer')
    return records, int.from_bytes(patch[pos:],'big') if pos<len(patch) else None

def main():
    p=argparse.ArgumentParser(); p.add_argument('--j',type=Path,required=True)
    p.add_argument('--k',type=Path,required=True);p.add_argument('--ips',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True); a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    j=a.j.read_bytes(); k=a.k.read_bytes(); patch=a.ips.read_bytes()
    records,truncate=ips_records(patch); replay=bytearray(j)
    covered=bytearray(max(len(j),len(k))); overlaps=[]
    for offset,data in records:
        if offset+len(data)>len(replay): replay.extend(bytes(offset+len(data)-len(replay)))
        if any(covered[offset:offset+len(data)]):overlaps.append(hex(offset))
        covered[offset:offset+len(data)]=bytes([1])*len(data)
        replay[offset:offset+len(data)]=data
    if truncate is not None: replay=replay[:truncate]
    diff=[i for i,(x,y) in enumerate(zip(j,k)) if x!=y]
    groups=[]
    for i in diff:
        if not groups or i-groups[-1][1]>32:groups.append([i,i+1,1])
        else:groups[-1][1]=i+1;groups[-1][2]+=1
    coarse=collections.Counter(i//0x10000 for i in diff)
    info={'j':identity(j),'k':identity(k),'ips':identity(patch),'ips_records':len(records),
          'ips_replay_identical':bytes(replay)==k,'ips_overlaps':overlaps,
          'changed_bytes_common_extent':len(diff),'groups_gap_max_32':len(groups),
          'header_j':j[0xa0:0xc0].hex(),'header_k':k[0xa0:0xc0].hex(),
          'changed_blocks_64k':{f'{b*0x10000:08X}':n for b,n in sorted(coarse.items())}}
    (a.out/'baseline.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    (a.out/'diff_groups.json').write_text(json.dumps([{'start':hex(s),'end':hex(e),'changed':n} for s,e,n in groups],indent=2),encoding='utf-8')
    pattern=re.compile(rb'(?:(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc])|[\x20-\x7e]){3,}')
    for label,rom in [('j',j),('k',k)]:
        rows=[]
        for m in pattern.finditer(rom):
            try: txt=m.group().decode('cp932')
            except UnicodeDecodeError: continue
            kana=sum('\u3040'<=c<='\u30ff' for c in txt)
            if kana<3 or kana/len(txt)<.3:continue
            rows.append(dict(offset=f'{m.start():08X}',size=len(m.group()),text=txt,
                             null_terminated=rom[m.end():m.end()+1]==b'\0',status='unclassified_candidate'))
        (a.out/f'{label}_sjis_candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        info[label+'_sjis_candidates']=len(rows)
    print(json.dumps(info,indent=2))
    print('LARGEST GROUPS',sorted(groups,key=lambda r:r[2],reverse=True)[:30])

if __name__=='__main__':main()
