"""One-time adoption of approved names inside proven opcode0F dialogue records.

Each replacement also requires the matching Japanese name in that very record.
The resulting explicit catalogs, not this search, are used by builds.
"""
import argparse,json,struct,re
from pathlib import Path
from dialogue_structure import source_records,ROOT
from text_codec import decode,encode
from dialogue_tokens import controls,unsafe_expansion_sequences

ALIASES=[('クラース','크라스'),('マリー','마리ー'),('リッド','릿드'),('キール','키르'),('チャット','챗'),('コレット','코렛'),('ゼロス','제로스'),('ジャババ','쟈바바'),('ワルキューレ','발키리'),('クレア','크레아'),('ジョニー','조니'),('ハロルド','해럴드')]

def replace_term(text,old,new,offset):
    # These suffixes were reviewed in the extracted sentences. Work at the
    # original alias occurrence so unrelated words such as 스킬 are untouched.
    particles={}
    if old in ('코렛','챗'):particles={'이라면':'라면','은':'는','이':'가','을':'를','과':'와'}
    if old=='키르':particles={'는':'은','가':'이','를':'을'}
    if old=='키르' and offset==0x197b60:particles['야']='이야' # "한 건 키르야" is a copula, not a vocative.
    pattern=re.compile(re.escape(old)+('('+ '|'.join(map(re.escape,sorted(particles,key=len,reverse=True))) +r')(?=[\s?!,…%]|$)|'+re.escape(old) if particles else ''))
    if not particles:return text.replace(old,new)
    return pattern.sub(lambda m:new+particles.get(m.group(1),''),text)

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--refresh-owned',action='store_true');a=p.parse_args()
    j=a.j.read_bytes();legacy=a.legacy.read_bytes();records=source_records(j,legacy)
    path=ROOT/'source/dialogue_fixes.json';profile=json.loads(path.read_text(encoding='utf-8'))
    catpath=ROOT/'translations/dialogue_fixes.json';catalog=json.loads(catpath.read_text(encoding='utf-8'))
    terms=json.loads((ROOT/'translations/terminology.json').read_text(encoding='utf-8'))['characters']
    out=ROOT/'translations/dialogue-term-changes.json'
    if out.exists() and not a.refresh_owned:raise ValueError('Existing adoption ledger requires explicit refresh-owned')
    existing={int(r['record_offset'],0):r for r in profile['records']};ledger=[];unresolved=[]
    for row in records:
        off=row['record_offset'];start=row['pointer']-0x08000000
        jr=j[start:j.index(0,start)];kr=legacy[start:legacy.index(0,start)];jp=decode(jr);text=decode(kr,True);selected=[]
        for name,alias in ALIASES:
            if alias not in text:continue
            if name not in jp:
                unresolved.append({'record_offset':hex(off),'alias':alias,'japanese_name':name});continue
            chosen=terms[name];selected.append({'japanese':name,'previous':alias,'selected':chosen,'occurrences':text.count(alias)})
            text=replace_term(text,alias,chosen,off)
        if not selected:continue
        if off in existing and (not a.refresh_owned or existing[off].get('kind')!='approved_character_terminology'):raise ValueError('Correction overlap requires explicit merge')
        raw=encode(text)
        if [t for _,t in controls(raw)]!=[t for _,t in controls(kr)] or raw.count(b'\n')!=kr.count(b'\n') or unsafe_expansion_sequences(raw):
            raise ValueError('Name adoption changed controls or introduces unsafe expansion')
        identity=f'dialogue-terms-{off:06x}'
        source_row={'id':identity,'record_offset':hex(off),'source_record':j[off:off+8].hex(),'j_raw':jr.hex(),'legacy_raw':kr.hex(),'kind':'approved_character_terminology','name_evidence':selected}
        target_row={'id':identity,'text':text,'review':'source_name_identity_user_wording_and_attached_particles_verified_layout_pending'}
        if off in existing:
            existing[off].update(source_row)
            target=next(r for r in catalog['records'] if r['id']==identity);target.update(target_row)
        else:
            profile['records'].append(source_row);catalog['records'].append(target_row)
        ledger.append({'record_offset':hex(off),'changes':selected})
    profile['scope']='Individually frozen opcode0F corrections and approved character terminology; consumer membership and original bytes validated on every build'
    path.write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8');catpath.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    with out.open('w' if a.refresh_owned else 'x',encoding='utf-8') as stream:json.dump({'authority':'User-provided character list and explicit conflict resolution; attached Korean particles adjusted only at reviewed alias occurrences','records':ledger,'unresolved_alias_records':unresolved},stream,ensure_ascii=False,indent=2)
    print(json.dumps({'selected_records':len(ledger),'unresolved_alias_records':unresolved},ensure_ascii=False))

if __name__=='__main__':main()
