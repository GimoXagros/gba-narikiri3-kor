"""Repoint reviewed mission win/loss fields through a guarded table."""
import hashlib
import json
import struct
from pathlib import Path

from text_codec import encode, decode

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_string(rom, address):
    start = address - 0x08000000
    if not 0 <= start < len(rom):
        raise ValueError('Mission text pointer outside source ROM')
    end = rom.find(b'\0', start, start + 128)
    if end < 0:
        raise ValueError('Mission text lacks bounded terminator')
    return rom[start:end]


def validate(japanese, legacy):
    profile = json.loads((ROOT/'source/mission_condition_profile.json').read_text('utf-8'))
    catalog = json.loads((ROOT/'translations/mission_conditions.json').read_text('utf-8'))
    if profile['schema'] != 1 or catalog['schema'] != 1 or catalog['policy'] != 'development_only_needs_review':
        raise ValueError('Mission condition profile/catalog schema differs')
    base, end = int(profile['table_base'], 0), int(profile['table_end'], 0)
    start, limit = int(profile['extension_start'], 0), int(profile['extension_end'], 0)
    if (base, end, start, limit) != (0x74C99C, 0x74CE88, 0x140000, 0x141000):
        raise ValueError('Mission condition table or allocation moved')
    for label, rom in [('japanese', japanese), ('legacy', legacy)]:
        if len(rom) != 0x1000000 or sha(rom) != profile[label+'_rom_sha256']:
            raise ValueError('Unsupported '+label+' ROM revision')
        if sha(rom[base:end]) != profile['table_sha256']:
            raise ValueError('Mission condition table differs')
        for kind in ('getter', 'display_caller'):
            off, raw = int(profile[kind+'_offset'], 0), bytes.fromhex(profile[kind+'_hex'])
            if rom[off:off+len(raw)] != raw:
                raise ValueError('Mission '+kind+' code differs')
    translations = {r['id']: r for r in catalog['groups']}
    if set(translations) != set(profile['groups']) or len(translations) != 13:
        raise ValueError('Mission condition group mismatch')
    for key, row in translations.items():
        source = profile['groups'][key]
        jp = source_string(japanese, int(source['japanese_pointer'], 0))
        kr = source_string(legacy, int(source['legacy_pointer'], 0))
        if (sha(jp), sha(kr)) != (source['japanese_raw_sha256'], source['legacy_raw_sha256']):
            raise ValueError('Mission condition source bytes differ: '+key)
        if decode(jp) != row['japanese'] or decode(kr, True) != source['legacy_text']:
            raise ValueError('Mission condition source meaning differs: '+key)
        text = row['text']
        if not text or len(text) > 18 or any(c in text for c in ('%', '@', '\n', '\r')):
            raise ValueError('Mission condition exceeds observed one-line 18-cell placement')
        if decode(encode(text), True) != text:
            raise ValueError('Mission condition does not round-trip: '+key)
    fields = profile['fields']
    if len(fields) != 75 or len({r['stable_id'] for r in fields}) != 75 or len({r['pointer_offset'] for r in fields}) != 75:
        raise ValueError('Expected 75 distinct reviewed pointer fields')
    from collections import Counter
    if Counter(r['group'] for r in fields) != {'team_defeat':44, 'turn_limit':5, 'two_teams':1, 'four_teams':1, 'find_key_next_floor':16,
            'defeat_barbatos':1, 'rescue_farah_keel':1, 'catch_pony_clight':1,
            'elder_house_defeat':1, 'zelos_sheena_defeat':1, 'thirty_turn_seven':1,
            'journey_key':1, 'key_stolen_defeat':1}:
        raise ValueError('Mission condition field group count changed')
    for row in fields:
        at = int(row['pointer_offset'], 0)
        if at % 4 or not base <= at < end or at+4 > end:
            raise ValueError('Mission condition field is outside aligned table')
        source = profile['groups'][row['group']]
        wanted = int(source['japanese_pointer'], 0)
        if struct.unpack_from('<I', japanese, at)[0] != wanted or struct.unpack_from('<I', legacy, at)[0] != wanted:
            raise ValueError('Mission condition pointer identity differs: '+row['stable_id'])
    return profile, catalog


def install(japanese, legacy, extension):
    profile, catalog = validate(japanese, legacy)
    start, limit = int(profile['extension_start'], 0), int(profile['extension_end'], 0)
    if extension[start:limit] != b'\xff'*(limit-start):
        raise ValueError('Mission condition text pool collision')
    # Prepare every allocation before mutating the pool or the ROM write plan.
    allocations, targets, cursor = [], {}, start
    for row in catalog['groups']:
        raw = encode(row['text']) + b'\0'
        if cursor + len(raw) > limit:
            raise ValueError('Mission condition text pool exhausted')
        allocations.append((cursor, raw))
        targets[row['id']] = 0x09000000 + cursor
        cursor = (cursor + len(raw) + 3) & ~3
    writes = [(int(row['pointer_offset'], 0), struct.pack('<I', targets[row['group']]),
               row['stable_id']+' mission loss condition') for row in profile['fields']]
    for offset, raw in allocations:
        extension[offset:offset+len(raw)] = raw
    return writes, {'selected_fields': len(writes), 'unique_phrases': len(allocations),
                    'text_start': hex(0x1000000+start), 'text_end': hex(0x1000000+cursor),
                    'source_table_sha256': profile['table_sha256'], 'scope': profile['scope']}
