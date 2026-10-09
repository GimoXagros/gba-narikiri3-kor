"""Source-bound, opt-in dialogue voice corrections for local candidates."""
import hashlib
import struct

from dialogue_structure import source_records
from dialogue_tokens import controls, unsafe_expansion_sequences, validate_dialogue_formats
from text_codec import decode, encode


def sha(data):
    return hashlib.sha256(data).hexdigest()


def selections(profile, j, legacy, baseline):
    if profile.get('schema') != 1 or profile.get('profile_version') != 'tone-pass01-20260930':
        raise ValueError('Unknown tone profile')
    if sha(baseline) != profile['baseline_rom_sha256'] or sha(j) != profile['source_japanese_rom_sha256']:
        raise ValueError('Tone source or baseline differs')
    indexed = {r['record_offset']: r for r in source_records(j, legacy)}
    result = []
    seen = set()
    for row in profile['changes']:
        off = int(row['binding_id'].split('-')[-1], 16)
        if row['decision'] != 'CORRECT' or off in seen or off not in indexed:
            raise ValueError('Duplicate, unindexed, or unsupported tone decision')
        seen.add(off)
        command = bytes.fromhex(row['source_record_hex'])
        if len(command) != 8 or j[off:off+8] != command or legacy[off:off+8] != command:
            raise ValueError('Tone source command differs: '+row['change_id'])
        if indexed[off]['speaker'] != row['speaker_id']:
            raise ValueError('Tone command identity differs: '+row['change_id'])
        source_ptr = struct.unpack_from('<I', command, 4)[0] - 0x08000000
        jp = j[source_ptr:j.index(0, source_ptr)]
        old = legacy[source_ptr:legacy.index(0, source_ptr)]
        if decode(jp) != row['japanese'] or sha(jp) != row['source_sha256'] or decode(old, korean=True) != row['before'] or sha(old) != row['before_sha256']:
            raise ValueError('Tone source payload differs: '+row['change_id'])
        base_ptr = struct.unpack_from('<I', baseline, off+4)[0] - 0x08000000
        before = baseline[base_ptr:baseline.index(0, base_ptr)]
        if before != old or baseline[off:off+4] != command[:4]:
            raise ValueError('Tone baseline binding differs: '+row['change_id'])
        new = encode(row['after'])
        if decode(new, korean=True) != row['after']:
            raise ValueError('Tone text encoding is not reversible')
        validate_dialogue_formats(new)
        if unsafe_expansion_sequences(new) or [t for _, t in controls(new)] != [t for _, t in controls(old)]:
            raise ValueError('Tone controls changed')
        if new.count(b'\n') != old.count(b'\n') or len(new) + 8*sum(t.startswith(b'@') for _,t in controls(new)) >= 256:
            raise ValueError('Tone page or expansion limit changed')
        result.append((row['change_id'], off+4, new+b'\0'))
    if len(result) != 3:
        raise ValueError('Tone pass01 decision count differs')
    return result
