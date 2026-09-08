"""Execute the original dialogue name expander with a bounded allocation fixture.

Only the heap allocator is substituted; expansion and strlen execute ROM code.
This does not establish natural-play reachability of every selected record.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode
from dialogue_tokens import expand_expected,unsafe_expansion_sequences

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); rom = a.rom.read_bytes()
    names = json.loads((ROOT/'translations/default_names.json').read_text(encoding='utf-8'))['names']
    for table in (0x741dc4, 0x741dd0):
        for i, name in enumerate(names):
            start = struct.unpack_from('<I', rom, table+i*4)[0]-0x08000000
            if rom[start:rom.index(0, start)] != encode(name):
                raise ValueError('New-game default name differs')
    if names[2] != '드림': raise ValueError('Ship templates require the base name without 호')
    profile = json.loads((ROOT/'source/dialogue_fixes.json').read_text(encoding='utf-8'))
    catalog = {r['id']: r['text'] for r in json.loads((ROOT/'translations/dialogue_fixes.json').read_text(encoding='utf-8'))['records']}
    sources = []
    for row in profile['records']:
        offset = int(row['record_offset'], 0)
        if rom[offset:offset+4] != bytes.fromhex(row['source_record'])[:4]:
            raise ValueError('Dialogue opcode or speaker changed')
        ptr = struct.unpack_from('<I', rom, offset+4)[0]; start = ptr-0x08000000
        raw = rom[start:rom.index(0, start)]
        if not 0x1080000 <= start < 0x1090000 or raw != encode(catalog[row['id']]):
            raise ValueError('Dialogue relocation differs')
        if unsafe_expansion_sequences(raw):raise ValueError('Unsafe multibyte trail in corrected dialogue')
        sources.append((row['id'], ptr, raw))
    # Preserve the legacy custom punctuation bytes in this unmodified message.
    start = 0x1ad31c
    sources.append(('observed-theft-line', start+0x08000000, rom[start:rom.index(0, start)]))
    f = Fixture(rom, 0); u = f.uc; allocations = []
    buf = 0x02010000
    def allocate(uc, address, size, data):
        allocations.append(uc.reg_read(UC_ARM_REG_R0))
        uc.reg_write(UC_ARM_REG_R0, buf)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, allocate, begin=0x0800356c, end=0x0800356c)
    u.mem_write(0x02001d60, struct.pack('<I', 0x02002000))
    samples = [encode('드림'), encode('가나다라마'), encode('가A나B다'), 'ドリーム'.encode('cp932'), b'DREAM']
    count = 0
    for ship in samples:
        u.mem_write(0x02002000, bytes(96))
        u.mem_write(0x02002013, ship+b'\0')
        u.mem_write(0x02002033, ship+b'\0')
        u.mem_write(0x02002053, ship+b'\0')
        u.mem_write(0x02003020,struct.pack('<II',0x02004000,0x02004020))
        u.mem_write(0x02004000,ship+b'\0');u.mem_write(0x02004020,ship+b'\0')
        for identity, ptr, raw in sources:
            u.mem_write(buf-16, b'\xa5'*288)
            u.reg_write(UC_ARM_REG_R0, 0x02003000); u.reg_write(UC_ARM_REG_R1, ptr)
            u.reg_write(UC_ARM_REG_SP, 0x03007e00); u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
            allocations.clear()
            u.emu_start(0x080c7669, 0x0203fff0, count=1000000)
            if u.reg_read(UC_ARM_REG_PC) != 0x0203fff0 or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
                raise ValueError('Name expander return/stack mismatch')
            expected = expand_expected(raw,{key:ship for key in (b'@B',b'@G',b'@D',b'@0',b'@1')})+b'\0'
            if allocations != [256] or u.reg_read(UC_ARM_REG_R0) != buf or len(expected)>256:
                raise ValueError('Allocation/return pointer contract differs')
            if bytes(u.mem_read(buf, len(expected))) != expected:
                raise ValueError('Name substitution or preserved punctuation differs: '+identity)
            if bytes(u.mem_read(buf-16, 16)) != b'\xa5'*16 or bytes(u.mem_read(buf+len(expected), 272-len(expected))) != b'\xa5'*(272-len(expected)):
                raise ValueError('Name expansion wrote beyond its terminated output')
            count += 1
    report = {'status':'PASS', 'rom_sha256':hashlib.sha256(rom).hexdigest(),
              'new_game_defaults_verified': names, 'selected_dialogue_records':len(profile['records']),
              'original_expander_cases':count, 'allocation_bytes':256,
              'guard_bytes_preserved':True,
              'scope':'Actual original Thumb name expansion and strlen; only allocator substituted. Every relocated dialogue record plus observed unchanged theft template. Natural-play and all other dialogue remain separate.'}
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__': main()
