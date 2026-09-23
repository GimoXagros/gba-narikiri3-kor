"""Freeze user-approved non-dialogue text fields from immutable source ROMs."""
import hashlib
import json
import struct
from pathlib import Path

from text_codec import decode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/dialogue-book-20260920'


def sha(data): return hashlib.sha256(data).hexdigest()


def source_string(rom, ptr):
    start=ptr-0x08000000
    if not 0 <= start < len(rom): raise ValueError('Pointer outside source ROM')
    end=rom.find(b'\0',start,start+512)
    if end<0: raise ValueError('Unterminated source UI string')
    return rom[start:end]


def main():
    j=next(ROOT.glob('*[[]J[]].gba')).read_bytes()
    k=next(ROOT.glob('*[[]K[]]_1.1.gba')).read_bytes()
    if sha(j)!='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394' or sha(k)!='8440f3e3db46c474c81cf84098798f07ab91aa13d48431c523c309a0af363010':
        raise ValueError('Unsupported source revision')
    decisions=json.loads((OUT/'review-decisions.json').read_text('utf-8'))
    ledger={r['stable_id']:r for r in map(json.loads,(OUT/'ledger.jsonl').read_text('utf-8').splitlines())}
    chosen=[]
    for identity,decision in decisions.items():
        row=ledger[identity]
        if row['kind']!='historical_text_consumer_unclassified' or decision.get('apply_status')!='approved':continue
        if not (decision.get('change_type','').startswith('시스템/UI') or identity in ('xlsx-919','xlsx-921')):continue
        offset=int(row['current_pointer'],16)
        if 0x74C99C <= offset < 0x74CE88:continue  # Mission condition table has its own verified writer.
        if not decision.get('rom'):raise ValueError('Missing approved UI text: '+identity)
        jp=struct.unpack_from('<I',j,offset)[0]
        kp=struct.unpack_from('<I',k,offset)[0]
        if jp!=kp:raise ValueError('UI pointer field differs: '+identity)
        jr,kr=source_string(j,jp),source_string(k,kp)
        if decode(jr)!=row['japanese'] or decode(kr,True)!=row['ko_current_raw']:
            raise ValueError('UI ledger source differs: '+identity)
        chosen.append((identity,offset,jp,jr,kr,decision['rom']))
    if len(chosen)!=32 or len({r[1] for r in chosen})!=32:
        raise ValueError('Expected exactly 32 separate approved non-mission UI pointers')
    chosen.sort(key=lambda r:r[1])
    profile={'schema':1,'japanese_rom_sha256':sha(j),'legacy_rom_sha256':sha(k),
        'extension_start':'0x141000','extension_end':'0x150000',
        'scope':'32 individually identified historical non-dialogue pointer fields; exact immutable source bytes and consumer pointers guarded. Screen navigation remains separate.',
        'fields':[{'stable_id':identity,'pointer_offset':hex(offset),'source_pointer':hex(ptr),
            'japanese_raw_sha256':sha(jr),'legacy_raw_sha256':sha(kr),
            'japanese':decode(jr),'legacy':decode(kr,True)}
            for identity,offset,ptr,jr,kr,_ in chosen]}
    catalog={'schema':1,'policy':'development_only_needs_review',
        'source_comparison':'User-confirmed wording at these 32 exact non-dialogue pointer fields; source string, token, line and width checks are enforced by the build.',
        'records':[{'stable_id':identity,'text':text} for identity,_,_,_,_,text in chosen]}
    (ROOT/'source/review_ui_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n','utf-8')
    (ROOT/'translations/review_ui.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'fields':len(chosen),'first':chosen[0][0],'last':chosen[-1][0]}))


if __name__=='__main__':main()
