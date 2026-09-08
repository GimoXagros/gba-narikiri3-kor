"""Remove false *edges* from PCM bytes, retaining every unresolved candidate.

Never adopts translations or rewrites the ROM. Sample lengths follow the
actual mixer at 080DB2CA/080DB302..30A, not a resemblance to Japanese text.
"""
import argparse,hashlib,json,struct
from bisect import bisect_right
from pathlib import Path
from nontext_contract import protected_regions,ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--candidates',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.j.read_bytes();profile=json.loads((ROOT/'source/nontext_profile.json').read_text(encoding='utf-8'))
    if hashlib.sha256(rom).hexdigest()!=profile['source_sha256']:raise ValueError('Wrong Japanese source')
    protected_regions(rom)
    for g in profile['consumer_guards']:
        off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
        if rom[off:off+len(raw)]!=raw:raise ValueError('PCM consumer/anchor differs')
    u=lambda off:struct.unpack_from('<I',rom,off)[0]
    region=profile['regions'][0];pos=int(region['start'],0);end=int(region['end'],0);samples=[]
    while pos<end:
        kind,status,freq,loop,length=struct.unpack_from('<HHIII',rom,pos)
        if kind or status not in (0,0x4000) or not 0<=loop<length or pos+16+length>end:raise ValueError('Unexpected WaveData header')
        owners=[i for i in range(0x1c40b8,0x1c81cc,4) if u(i)==0x08000000+pos and rom[i-4]&0xc7==0]
        if not owners:raise ValueError('Sample has no direct PCM ToneData reference')
        samples.append({'header':hex(pos),'data_start':pos+16,'data_end':pos+16+length,'tone_pointer_offsets':[hex(i) for i in owners]})
        # Authoring storage includes a terminal sample/padding byte and 4-byte
        # alignment; this is storage layout, not extra samples to translate.
        pos=(pos+16+length+4)&~3
    if pos!=end or len(samples)!=region['sample_count']:raise ValueError('Sample population/terminal boundary differs')
    starts=[s['data_start'] for s in samples]
    rows=json.loads(a.candidates.read_text(encoding='utf-8'));classified=[];excluded=0;excluded_failures=0
    for row in rows:
        edges=[]
        for owner in row['reference_candidates']:
            off=int(owner,16);idx=bisect_right(starts,off)-1
            sample=samples[idx] if idx>=0 and off+4<=samples[idx]['data_end'] else None
            edges.append({'offset':owner,'state':'pcm_bytes_not_a_pointer' if sample else 'unresolved','sample_header':sample['header'] if sample else None})
        all_pcm=all(e['state']=='pcm_bytes_not_a_pointer' for e in edges)
        excluded+=all_pcm;excluded_failures+=all_pcm and row['k_text'] is None
        classified.append({'id':row['id'],'target_offset':row['offset'],'state':'no_non_audio_reference_in_this_scan' if all_pcm else 'unresolved','edges':edges})
    out={'status':'CLASSIFICATION_ONLY_NOT_TRANSLATION_POPULATION','source_sha256':profile['source_sha256'],'scan_sha256':hashlib.sha256(a.candidates.read_bytes()).hexdigest(),'sample_count':len(samples),'scanned_candidates':len(rows),'candidates_with_only_pcm_edges':excluded,'decode_failures_with_only_pcm_edges':excluded_failures,'remaining_candidates':len(rows)-excluded,'samples':samples,'candidates':classified,'limits':'A genuine string may have additional references outside this scan. This rejects PCM-derived references, never the underlying string solely because this scan missed a caller.'}
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('samples','candidates','limits')}))
if __name__=='__main__':main()
