"""Read the frozen indexed VM resource; report unresolved text issues separately."""
import argparse,hashlib,json,re
from pathlib import Path
from dialogue_structure import source_records
from dialogue_tokens import controls,unsafe_expansion_sequences
from text_codec import decode,encode

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    j=a.j.read_bytes();legacy=a.legacy.read_bytes();records=source_records(j,legacy);rows=[];issues=[];roundtrips=0;unchanged=[]
    for record in records:
        row={**record,'record_offset':hex(record['record_offset']),'pointer':hex(record['pointer'])}
        start=record['pointer']-0x08000000
        for key,rom,is_k in [('j',j,False),('legacy',legacy,True)]:
            end=rom.find(b'\0',start,start+4096)
            if end<0:raise ValueError('Unterminated adopted dialogue')
            raw=rom[start:end];row[key+'_raw']=raw.hex();row[key+'_text']=decode(raw,is_k)
            row[key+'_controls']=[t.decode('ascii') for _,t in controls(raw)]
        raw=bytes.fromhex(row['legacy_raw'])
        try:equal=encode(row['legacy_text'])==raw
        except (ValueError,UnicodeError):equal=False
        roundtrips+=equal
        if not equal:issues.append({'record':row['record_offset'],'type':'codec_roundtrip'})
        if row['j_raw']==row['legacy_raw']:unchanged.append(row['record_offset'])
        if [x for x in row['j_controls'] if x.startswith('@')]!=[x for x in row['legacy_controls'] if x.startswith('@')]:
            issues.append({'record':row['record_offset'],'type':'name_substitution_changed_review_meaning'})
        if unsafe_expansion_sequences(raw):issues.append({'record':row['record_offset'],'type':'multibyte_trail_invokes_name_expansion','offsets':unsafe_expansion_sequences(raw)})
        kana=[c for c in row['legacy_text'] if ('\u3040'<=c<='\u30ff' and c not in 'ー・') or '\uff61'<=c<='\uff9f']
        if kana:issues.append({'record':row['record_offset'],'type':'kana_review','characters':''.join(kana)})
        rows.append(row)
    report={'status':'INDEXED_DIALOGUE_EXTRACTED_NOT_FULL_GAME_TRANSLATION_CLAIM','script_count':1000,'dialogue_record_count':len(rows),'unique_payload_count':len({r['pointer'] for r in rows}),
            'legacy_decode_encode_roundtrips':roundtrips,'unchanged_records':unchanged,'issues':issues,'records':rows,
            'scope':'Every opcode0F and opcode25 dialogue record in the frozen 1000-entry VM table. Empty and punctuation-only strings are retained. Does not include other UI tables, graphics, or prove every script reachable.'}
    with a.out.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','issues','unchanged_records')},ensure_ascii=False))
    print(json.dumps({'issues':len(issues),'unchanged':len(unchanged)},ensure_ascii=False))

if __name__=='__main__':main()
