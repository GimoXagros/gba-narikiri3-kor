"""Conservative v1.2 dialogue inventory and source-bound in-place overlay.

The proven writable span is the current encoded payload plus its terminator.
Adjacent zero/FF padding is never claimed as string capacity. This tool does
not rebuild, repack, relocate, deduplicate or alter any VM pointer.
"""
import argparse
import bisect
import hashlib
import json
import struct
from pathlib import Path

from dialogue_structure import source_records
from dialogue_tokens import controls, unsafe_expansion_sequences, validate_dialogue_formats
from text_codec import decode, encode
from classify_text_candidates import verified_pcm_samples

PUBLIC_V12_SHA256='8953b6a98a9b39e340aecdc74739598ee47c4d59088f688e471a81c289a67793'
PUBLIC_V12_SIZE=0x2000000
ROOT=Path(__file__).resolve().parents[1]


def sha(data):return hashlib.sha256(data).hexdigest()


def cstr(rom,off):
    if not 0<=off<len(rom):raise ValueError('Dialogue pointer outside v1.2 ROM')
    end=rom.find(b'\0',off,min(off+8192,len(rom)))
    if end<0:raise ValueError('No bounded dialogue terminator: '+hex(off))
    return rom[off:end]


def inventory(j,legacy,baseline):
    if len(baseline)!=PUBLIC_V12_SIZE or sha(baseline)!=PUBLIC_V12_SHA256:
        raise ValueError('Expected exact public v1.2 32 MiB baseline')
    typed=source_records(j,legacy)
    groups={};rows=[]
    for record in typed:
        off=record['record_offset'];ptr=struct.unpack_from('<I',baseline,off+4)[0]
        if not 0x08000000<=ptr<0x0a000000:raise ValueError('Non-ROM dialogue pointer: '+hex(off))
        start=ptr-0x08000000;raw=cstr(baseline,start);command=baseline[off:off+8]
        if command[:4]!=j[off:off+4]:raise ValueError('v1.2 VM opcode/speaker differs: '+hex(off))
        item={'record_offset':hex(off),'script_index':record['script_index'],'speaker_id':record['speaker'],
              'baseline_command_hex':command.hex(),'baseline_pointer':hex(ptr),'storage_offset':hex(start),
              'before_sha256':sha(raw),'before_text':decode(raw,korean=True),'before_bytes':raw.hex(),
              'before_encoded_bytes':len(raw),
              'safe_capacity_bytes':len(raw),'terminator_offset':hex(start+len(raw)),
              'after_terminator_capacity_bytes_proven':0,
              'japanese_sha256':sha(cstr(j,record['pointer']-0x08000000))}
        rows.append(item);groups.setdefault(start,[]).append(item)
    starts=sorted(groups)
    ends={start:start+groups[start][0]['before_encoded_bytes'] for start in starts}
    for start,items in groups.items():
        if any(x['before_sha256']!=items[0]['before_sha256'] for x in items):
            raise ValueError('Shared pointer produced different baseline text')
    overlaps=[]
    for a,b in zip(starts,starts[1:]):
        if b<=ends[a]:overlaps.append({'first':hex(a),'second':hex(b),'first_end':hex(ends[a])})
    # Inspect every four-byte window, including unaligned words and all GBA
    # ROM mirror regions. A match is a possible reference, not proof of use.
    refs={start:[] for start in starts}
    indexed_fields={start:{int(r['record_offset'],0)+4 for r in groups[start]} for start in starts}
    nontext=json.loads((ROOT/'source/nontext_profile.json').read_text(encoding='utf-8'))
    pcm=next(r for r in nontext['regions'] if r['id']=='m4a-pcm-sample-bank')
    pcm_start,pcm_end=int(pcm['start'],0),int(pcm['end'],0)
    if sha(baseline[pcm_start:pcm_end])!=pcm['sha256']:
        raise ValueError('Protected PCM bank differs; cannot classify pointer-shaped sample bytes')
    samples,_=verified_pcm_samples(j)
    sample_starts=[s['data_start'] for s in samples]
    for at in range(len(baseline)-3):
        value=struct.unpack_from('<I',baseline,at)[0]
        if value>>24 not in (8,9,10,11,12,13):continue
        physical=value&0x01ffffff
        index=bisect.bisect_right(starts,physical)-1
        if index<0:continue
        start=starts[index]
        if physical<=ends[start]:
            sample_index=bisect.bisect_right(sample_starts,at)-1
            sample=(samples[sample_index] if sample_index>=0 and at+4<=samples[sample_index]['data_end'] else None)
            kind=('INDEXED_VM_BINDING' if at in indexed_fields[start] and physical==start else
                  'VERIFIED_PCM_SAMPLE_PAYLOAD_BYTES' if sample else
                  'UNCLASSIFIED_POINTER_LIKE')
            refs[start].append({'word_offset':hex(at),'pointer_value':hex(value),
                                'interior_bytes':physical-start,
                                'kind':kind,'pcm_sample_header':sample['header'] if sample else None,
                                'pcm_tone_pointer_offsets':sample['tone_pointer_offsets'] if sample else []})
    storage=[]
    for start in starts:
        items=groups[start];found=refs[start]
        indexed=indexed_fields[start]
        if not indexed.issubset({int(r['word_offset'],0) for r in found}):
            raise ValueError('Indexed VM reference missing from whole-ROM scan')
        storage.append({'storage_offset':hex(start),'baseline_pointer':items[0]['baseline_pointer'],
                        'before_sha256':items[0]['before_sha256'],
                        'safe_capacity_bytes':items[0]['safe_capacity_bytes'],
                        'binding_offsets':[r['record_offset'] for r in items],
                        'shared_indexed_bindings':len(items),
                        'pointer_like_references':found,
                        'unclassified_pointer_like_count':sum(r['kind']=='UNCLASSIFIED_POINTER_LIKE' for r in found),
                        'interior_pointer_like_count':sum(r['interior_bytes']!=0 for r in found),
                        'unresolved_interior_pointer_like_count':sum(r['interior_bytes']!=0 and r['kind']=='UNCLASSIFIED_POINTER_LIKE' for r in found),
                        'classified_pcm_sample_coincidences':sum(r['kind']=='VERIFIED_PCM_SAMPLE_PAYLOAD_BYTES' for r in found),
                        'overlaps_another_indexed_payload':any(x['first']==hex(start) or x['second']==hex(start) for x in overlaps)})
    return {'schema':1,'baseline_identity':'public-v1.2-32MiB','baseline_sha256':sha(baseline),
            'baseline_bytes':len(baseline),'capacity_policy':'ONLY_EXISTING_PAYLOAD_PLUS_TERMINATOR; adjacent padding unproven',
            'typed_bindings':len(rows),'unique_storage_strings':len(storage),
            'overlapping_indexed_spans':overlaps,'records':rows,'storage':storage,
            'pointer_scan_scope':'Every four-byte window in the 32 MiB ROM; 08/09/0A/0B/0C/0D mirror-like words. Only words wholly inside a verified WaveData sample payload, with direct ToneData owner and guarded PCM consumer, are classified as audio-data coincidences. Header/padding words remain unresolved.'}


def plan_overlay(baseline,book,profile):
    if profile.get('schema')!=1 or profile.get('baseline_sha256')!=PUBLIC_V12_SHA256 or profile.get('baseline_bytes')!=PUBLIC_V12_SIZE:
        raise ValueError('In-place profile is not bound to public v1.2')
    if sha(baseline)!=profile['baseline_sha256'] or len(baseline)!=profile['baseline_bytes']:
        raise ValueError('Overlay baseline differs')
    if book['baseline_sha256']!=profile['baseline_sha256'] or book['baseline_bytes']!=len(baseline):
        raise ValueError('Inventory/baseline identity differs')
    if len(book['records'])!=5208 or len({r['record_offset'] for r in book['records']})!=5208:
        raise ValueError('Incomplete or duplicate v1.2 dialogue inventory')
    for row in book['records']:
        off=int(row['record_offset'],0)
        if not 0<=off<=len(baseline)-8 or baseline[off:off+8].hex()!=row['baseline_command_hex']:
            raise ValueError('Inventory VM command differs from actual baseline')
        ptr=struct.unpack_from('<I',baseline,off+4)[0]
        start=ptr-0x08000000
        if ptr!=int(row['baseline_pointer'],0) or start!=int(row['storage_offset'],0):
            raise ValueError('Inventory pointer/storage differs from actual baseline')
        raw=cstr(baseline,start)
        if (len(raw)!=row['before_encoded_bytes'] or len(raw)!=row['safe_capacity_bytes'] or
            sha(raw)!=row['before_sha256'] or raw.hex()!=row['before_bytes'] or
            decode(raw,korean=True)!=row['before_text']):
            raise ValueError('Inventory capacity/hash differs from actual baseline')
    by_record={int(r['record_offset'],0):r for r in book['records']}
    by_storage={int(s['storage_offset'],0):s for s in book['storage']}
    proposals={};change_ids=set()
    for change in profile['changes']:
        off=int(change['record_offset'],0)
        change_id=change.get('change_id')
        if (off in proposals or off not in by_record or change.get('decision')!='CORRECT' or
            not isinstance(change_id,str) or not change_id or change_id in change_ids or
            not isinstance(change.get('reason'),str) or not change['reason'].strip()):
            raise ValueError('Duplicate, unindexed or unapproved change')
        change_ids.add(change_id)
        row=by_record[off]
        if (change['baseline_command_hex']!=row['baseline_command_hex'] or
            change['before_sha256']!=row['before_sha256'] or
            change['speaker_id']!=row['speaker_id'] or
            change['japanese_sha256']!=row['japanese_sha256']):
            raise ValueError('Baseline readback/source identity differs: '+hex(off))
        raw=encode(change['after'])
        if b'\0' in raw:raise ValueError('Embedded NUL in proposed tone text: '+hex(off))
        if decode(raw,korean=True)!=change['after']:
            raise ValueError('Non-reversible tone text: '+hex(off))
        validate_dialogue_formats(raw)
        start=int(row['storage_offset'],0)
        old=baseline[start:start+row['before_encoded_bytes']]
        if sha(old)!=row['before_sha256'] or baseline[start+len(old)]!=0:
            raise ValueError('Inventory payload no longer matches baseline')
        if len(raw)>row['safe_capacity_bytes']:
            raise ValueError(f'INPLACE_OVER_BUDGET {hex(off)}: {len(raw)} > {row["safe_capacity_bytes"]}')
        if ([t for _,t in controls(raw)]!=[t for _,t in controls(old)] or
            raw.count(b'\n')!=old.count(b'\n') or unsafe_expansion_sequences(raw)):
            raise ValueError('Dialogue token/newline safety differs: '+hex(off))
        if len(raw)+8*sum(t.startswith(b'@') for _,t in controls(raw))>=256:
            raise ValueError('Name expansion exceeds established buffer')
        proposals[off]=(start,raw,change['change_id'])
    writes=[]
    for start,storage in by_storage.items():
        bound={int(x,0) for x in storage['binding_offsets']}
        selected=bound & proposals.keys()
        if not selected:continue
        if selected!=bound:raise ValueError('CONTEXT_SHARED_TEXT_CONFLICT: incomplete binding set at '+hex(start))
        values={proposals[off][1] for off in selected}
        if len(values)!=1:raise ValueError('CONTEXT_SHARED_TEXT_CONFLICT: different text for shared storage')
        if storage['unclassified_pointer_like_count'] or storage['unresolved_interior_pointer_like_count'] or storage['overlaps_another_indexed_payload']:
            raise ValueError('Unresolved external/interior/overlapping reference at '+hex(start))
        new=values.pop();old_len=storage['safe_capacity_bytes']
        data=new+b'\0'+b'\0'*(old_len-len(new))
        if len(data)!=old_len+1:raise AssertionError('In-place span differs')
        writes.append({'storage_offset':start,'data':data,'bindings':sorted(selected),'change_ids':[proposals[x][2] for x in sorted(selected)]})
    if len({x for w in writes for x in w['bindings']})!=len(proposals):
        raise ValueError('Some approved bindings were not placed')
    occupied=set()
    for w in writes:
        span=set(range(w['storage_offset'],w['storage_offset']+len(w['data'])))
        if occupied & span:raise ValueError('Overlapping in-place writes')
        occupied.update(span)
    return writes


def apply_overlay(baseline,book,profile):
    writes=plan_overlay(baseline,book,profile)
    out=bytearray(baseline)
    for w in writes:
        start=w['storage_offset'];out[start:start+len(w['data'])]=w['data']
    if len(out)!=len(baseline):raise AssertionError('ROM size changed')
    allowed={i for w in writes for i in range(w['storage_offset'],w['storage_offset']+len(w['data']))}
    if any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(baseline,out))):
        raise AssertionError('Unexpected ROM byte changed')
    selected={x for w in writes for x in w['bindings']}
    for row in book['records']:
        off=int(row['record_offset'],0)
        if out[off:off+8]!=baseline[off:off+8]:raise AssertionError('VM pointer/instruction changed')
        ptr=struct.unpack_from('<I',baseline,off+4)[0]-0x08000000
        if off not in selected and cstr(out,ptr)!=cstr(baseline,ptr):
            raise AssertionError('Unselected indexed dialogue payload changed')
    return bytes(out),writes


def validate_fresh_inventory(j,legacy,baseline,book):
    recomputed=inventory(j,legacy,baseline)
    if book!=recomputed:raise ValueError('Inventory differs from fresh source-bound v1.2 scan')
    return recomputed


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('inventory')
    for name in ('j','legacy','baseline','out'):q.add_argument('--'+name,type=Path,required=True)
    q=sub.add_parser('apply')
    for name in ('j','legacy','baseline','inventory','profile','out'):q.add_argument('--'+name,type=Path,required=True)
    q.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.command=='inventory':
        result=inventory(a.j.read_bytes(),a.legacy.read_bytes(),a.baseline.read_bytes())
        a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('records','storage','overlapping_indexed_spans')},ensure_ascii=False))
    else:
        if a.out.resolve()==a.report.resolve() or a.out.exists() or a.report.exists():
            p.error('Distinct fresh output and report files required')
        baseline=a.baseline.read_bytes();book=json.loads(a.inventory.read_text(encoding='utf-8'))
        validate_fresh_inventory(a.j.read_bytes(),a.legacy.read_bytes(),baseline,book)
        profile=json.loads(a.profile.read_text(encoding='utf-8'))
        out,writes=apply_overlay(baseline,book,profile)
        allowed={i for w in writes for i in range(w['storage_offset'],w['storage_offset']+len(w['data']))}
        changed=[i for i,(old,new) in enumerate(zip(baseline,out)) if old!=new]
        selected={off for w in writes for off in w['bindings']}
        report={'status':'LOCAL_INPLACE_CANDIDATE_NOT_RELEASE','baseline_sha256':sha(baseline),
                'inventory_sha256':sha(a.inventory.read_bytes()),'profile_sha256':sha(a.profile.read_bytes()),
                'rom_sha256':sha(out),'rom_bytes':len(out),'original_rom_bytes':len(baseline),
                'changed_storage_strings':len(writes),'changed_byte_count':len(changed),
                'nonpayload_changed_bytes':sum(i not in allowed for i in changed),
                'indexed_vm_pointer_and_command_fields_checked':len(book['records']),
                'indexed_vm_pointer_and_command_fields_changed':0,
                'unselected_indexed_payloads_checked':len(book['records'])-len(selected),
                'unselected_indexed_payloads_changed':0,
                'writes':[{'storage_offset':hex(w['storage_offset']),'bytes':len(w['data']),
                           'bindings':[hex(x) for x in w['bindings']],'change_ids':w['change_ids']} for w in writes]}
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_bytes(out)
        a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='writes'},ensure_ascii=False))


if __name__=='__main__':main()
