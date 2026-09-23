"""Bind the semantic review ledger to the immutable sources and emitted ROM."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from dialogue_structure import source_records
from dialogue_tokens import controls, unsafe_expansion_sequences
from text_codec import decode, encode
from review_dialogue_layouts import approved as approved_layout

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(j, legacy, target, audit):
    if sha(j) != audit['j_sha256'] or sha(legacy) != audit['legacy_sha256']:
        raise ValueError('Review source identity differs')
    typed = source_records(j, legacy)
    offsets = {r['record_offset'] for r in typed}
    reviewed = [int(s, 0) for s in audit['reviewed_records']]
    if len(reviewed) != len(set(reviewed)) or set(reviewed) != offsets or len(typed) != 5208:
        raise ValueError('Review denominator differs from typed dialogue consumers')
    changed = set()
    restored_waits = restored_names = 0
    for change in audit['changes']:
        new = encode(change['after'])
        if decode(new, korean=True) != change['after'] or unsafe_expansion_sequences(new):
            raise ValueError('Text encoding is not reversible or name expansion is unsafe')
        for line in change['after'].split('\n'):
            display = re.sub(r'%[kl]', '', line)
            display = re.sub(r'@[01BDGKL]', '가나다라마', display)
            if len(display) > 18:
                raise ValueError('Corrected line exceeds 18 cells with maximum-length names')
        for label in change['record_offsets']:
            off = int(label, 0)
            if off in changed or off not in offsets:
                raise ValueError('Duplicate or untyped correction')
            changed.add(off)
            start = struct.unpack_from('<I', j, off + 4)[0] - 0x08000000
            jr, kr = (rom[start:rom.index(0, start)] for rom in (j, legacy))
            if decode(jr) != change['japanese'] or decode(kr, korean=True) != change['before_v11']:
                raise ValueError('Ledger no longer matches the immutable original text')
            ptr = struct.unpack_from('<I', target, off + 4)[0] - 0x08000000
            if not 0 <= ptr < len(target) or target[ptr:ptr+len(new)+1] != new + b'\0':
                raise ValueError('Corrected text not present at its consumer pointer: '+change.get('stable_id','?')+' '+hex(off))
            if target[off:off+4] != j[off:off+4]:
                raise ValueError('Non-pointer opcode/speaker metadata changed')
            ref = [[token for _, token in controls(raw)] for raw in (jr, kr)]
            if [token for _, token in controls(new)] not in ref:
                raise ValueError('Control sequence does not match an immutable source')
            extra_scroll=(change.get('allow_extra_scroll') is True and approved_layout(change['stable_id'],change['after']))
            if not extra_scroll and new.count(b'\n') not in (jr.count(b'\n'), kr.count(b'\n')):
                raise ValueError('Unapproved newline structure')
            restored_waits += max(0, new.count(b'%k') - kr.count(b'%k'))
            restored_names += max(0, sum(t.startswith(b'@') for _, t in controls(new)) - sum(t.startswith(b'@') for _, t in controls(kr)))
    if len(changed) != audit['corrected_records'] or len(audit['changes']) != audit['correction_groups']:
        raise ValueError('Correction counts differ')
    return {'status': 'PASS', 'rom_sha256': sha(target), 'reviewed_typed_records': len(typed),
            'unique_pairs_read': audit['unique_pairs'], 'correction_groups': len(audit['changes']),
            'corrected_records': len(changed), 'restored_wait_commands_vs_v11': restored_waits,
            'restored_name_calls_vs_v11': restored_names,
            'maximum_corrected_line_cells': 18,
            'scope': 'Ledger/source/target identity, all corrected text bytes, guarded opcode/speaker metadata, controls, maximum-name line width. Semantic review is recorded separately; this check does not prove translation quality or natural reachability.'}


def main():
    p = argparse.ArgumentParser()
    for arg in ('j', 'legacy', 'rom', 'out'):
        p.add_argument('--' + arg, type=Path, required=True)
    p.add_argument('--audit', type=Path, default=ROOT / 'qa/dialogue-review-v1.1a.json')
    a = p.parse_args()
    path = a.audit
    audit = json.loads(path.read_text(encoding='utf-8'))
    result = verify(a.j.read_bytes(), a.legacy.read_bytes(), a.rom.read_bytes(), audit)
    result['ledger_sha256'] = sha(path.read_bytes())
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
