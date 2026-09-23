"""Verify all 75 mission-condition references and their actual lookup/render path."""
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

from mission_condition_text import validate, source_string
from text_codec import encode, decode
from verify_small_consumer import Fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--j', type=Path, required=True)
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    rom, japanese, legacy = a.rom.read_bytes(), a.j.read_bytes(), a.legacy.read_bytes()
    profile, catalog = validate(japanese, legacy)
    base, end = int(profile['table_base'], 0), int(profile['table_end'], 0)
    by_group = {row['id']: row['text'] for row in catalog['groups']}
    selected = {int(row['pointer_offset'], 0): row for row in profile['fields']}
    if len(rom) != 0x2000000:
        raise ValueError('Not a 32 MiB development ROM')
    # The entire 45-entry mission table must be unchanged except for the
    # four-byte pointer fields explicitly selected by the user.
    changed = {i for i in range(base, end) if rom[i] != legacy[i]}
    allowed = {i for offset in selected for i in range(offset, offset+4)}
    if changed - allowed or not changed:
        raise ValueError('Mission table has an unplanned difference')
    targets = {}
    for offset, row in selected.items():
        ptr = struct.unpack_from('<I', rom, offset)[0]
        value = by_group[row['group']]
        if not 0x09140000 <= ptr < 0x09141000 or source_string(rom, ptr) != encode(value):
            raise ValueError('Mission condition pointer or bytes differ: '+row['stable_id'])
        if decode(source_string(rom, ptr), True) != value:
            raise ValueError('Mission condition text failed decode: '+row['stable_id'])
        targets.setdefault(row['group'], ptr)
        if targets[row['group']] != ptr:
            raise ValueError('Shared phrase did not share one allocation')
    for off in range(base, end, 4):
        if off not in selected and rom[off:off+4] != legacy[off:off+4]:
            raise ValueError('Unselected mission field changed')
    if len(targets) != 13:
        raise ValueError('Thirteen source phrases were not adopted')

    getter_cases = 0
    render_cases = 0
    for mode in (0, 1):
        fixture = Fixture(rom, mode)
        u = fixture.uc
        # The original bit-flag accessor at 0800816C follows this IWRAM
        # pointer. Give it a bounded, zeroed fixture bitset.
        u.mem_write(0x02001d68, struct.pack('<I', 0x02003000))
        # Original 08009B88 getter: mission index -> two condition pointers.
        # Exercise every one of the 45 28-byte mission records, with the
        # default branch state. Alternate flag branches remain in the static
        # pointer-table check above.
        for mission in range(45):
            output = 0x02002000
            u.mem_write(output, b'\0'*8)
            u.reg_write(UC_ARM_REG_R0, mission)
            u.reg_write(UC_ARM_REG_R1, output)
            u.reg_write(UC_ARM_REG_SP, 0x03007e00)
            u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
            u.emu_start(0x08009b89, 0x0203fff0, count=100000)
            if u.reg_read(UC_ARM_REG_PC) != 0x0203fff0 or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
                raise ValueError('Mission condition getter did not return cleanly')
            first, second = struct.unpack('<II', u.mem_read(output, 8))
            possible = {struct.unpack_from('<I', rom, base+mission*28+x)[0] for x in (12,16,20,24)}
            if first not in possible or second not in possible:
                raise ValueError(f'Mission {mission} condition getter returned {first:08X}/{second:08X}; table {sorted(possible)}')
            getter_cases += 1
        for phrase in by_group.values():
            # The observed UI starts at x=24 pixels and uses 12-pixel text
            # cells, leaving 18 cells before the 240-pixel edge.
            if len(phrase) > 18:
                raise ValueError('Mission phrase crosses display edge')
            fixture.draw(encode(phrase), x=2, y=1)
            if fixture.tile(2+len(phrase)-1, 1) == bytes(32):
                raise ValueError('Final mission glyph was not rendered')
            render_cases += 1
    result = {'status':'PASS', 'rom_sha256':hashlib.sha256(rom).hexdigest(),
              'reviewed_fields':len(selected), 'unique_replacements':len(targets),
              'distribution':dict(Counter(row['group'] for row in profile['fields'])),
              'original_getter_cases':getter_cases, 'renderer_mode_cases':render_cases,
              'table_metadata_unchanged':True, 'actual_last_glyph_within_240px':True,
              'scope':'All 75 static table fields/bytes, original getter default branch for 45 missions, thirteen phrases in both rendering modes. Natural stage navigation and alternate mission-flag branches remain separate.'}
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
