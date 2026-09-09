"""Execute original resource-440 lookup/load on legacy and localized fonts."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

from verify_small_consumer import Fixture
from verify_inspect_eye import unpack_rle

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rom, old = args.rom.read_bytes(), args.legacy.read_bytes()
    profile = json.loads((ROOT / 'source/element_symbol_profile.json').read_text('utf-8'))
    inspection = json.loads((ROOT / 'source/inspect_eye_profile.json').read_text('utf-8'))
    labels = json.loads((ROOT / 'translations/element_symbols.json').read_text('utf-8'))['records']
    glyphs = json.loads((ROOT / 'fonts/dalmoori-wansung.json').read_text('utf-8'))
    bank, entry = 0xd4524c, 0xd456b8
    count = struct.unpack_from('<I', old, bank)[0]
    for idx in range(count):
        at = bank + 4 + idx * 4
        if idx != 282 and rom[at:at + 4] != old[at:at + 4]:
            raise ValueError('An unrelated affine graphics bank pointer changed')
    at = 0x1448e4
    if rom[at:at + 86 * 8] != old[at:at + 86 * 8]:
        raise ValueError('Affine resource ownership changed')
    for g in inspection['guards']:
        at = int(g['offset'], 0)
        if at in (0x168c8,):
            continue  # Producer/renderer entry modifications are checked by their verifier.
        if rom[at:at + len(bytes.fromhex(g['hex']))] != bytes.fromhex(g['hex']):
            raise ValueError('Original resource loader or symbol lookup changed')
    new_at = bank + struct.unpack_from('<I', rom, entry)[0]
    if not 0x1111000 <= new_at < 0x1115000:
        raise ValueError('Localized font is outside its declared allocation')
    original = unpack_rle(old, 0xd86384)
    wanted = bytearray(original)
    for row, source in zip(labels, profile['records'], strict=True):
        if row['id'] != source['id'] or row['source_symbol'] != source['symbol']:
            raise ValueError('Element identity/order differs')
        pixels = bytes(0xaf if p == '#' else 0xa1 for line in glyphs[row['compact']] for p in line)
        if len(pixels) != 64:
            raise ValueError('Element glyph geometry differs')
        wanted[source['tile'] * 64:(source['tile'] + 1) * 64] = pixels
    if unpack_rle(rom, new_at) != wanted:
        raise ValueError('Localized inspection font differs outside chosen symbol pixels')
    loads = []
    for name, image, expected in [('legacy', old, original), ('localized', rom, bytes(wanted))]:
        f = Fixture(image, 0)
        u = f.uc
        u.mem_write(0x02000104, struct.pack('<I', 0x02010000))
        u.mem_write(0x02010000, b'\xcc' * 320)
        u.mem_write(0x06000000, b'\x5a' * 0x18000)
        u.mem_write(0x05000000, b'\x3c' * 1024)
        events = []

        def bios(uc, number, data):
            pc = uc.reg_read(UC_ARM_REG_PC)
            instruction = bytes(uc.mem_read(pc - 2, 2))
            source, dest, control = (uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            if instruction == b'\x15\xdf':
                expected_source = 0x08000000 + bank + struct.unpack_from('<I', image, entry)[0]
                if source != expected_source or dest != 0x06008000:
                    raise ValueError('Original font source/upload path differs')
                header = int.from_bytes(uc.mem_read(source, 4), 'little')
                if header != 0x3c0030:
                    raise ValueError('Original decoded font extent changed')
                end = source + (15484 if name == 'localized' else 7972)
                output, cursor = bytearray(), source + 4
                while len(output) < 15360:
                    if cursor >= end:
                        raise ValueError('RLE control outside stored resource')
                    flag = uc.mem_read(cursor, 1)[0]
                    cursor += 1
                    length = (flag & 127) + 3 if flag & 128 else flag + 1
                    amount = 1 if flag & 128 else length
                    if cursor + amount > end or len(output) + length > 15360:
                        raise ValueError('RLE run outside input/output resource')
                    output.extend(bytes(uc.mem_read(cursor, 1)) * length if flag & 128 else uc.mem_read(cursor, length))
                    cursor += amount
                uc.mem_write(dest, bytes(output))
                events.append('RLUnCompVram-15360')
            elif instruction == b'\x0b\xdf':
                if (source, dest, control) != (0x08d882a8, 0x05000140, 0x04000010):
                    raise ValueError('Original palette CpuSet differs')
                uc.mem_write(dest, bytes(uc.mem_read(source, 64)))
                events.append('CpuSet-palette-64')
            else:
                raise ValueError('Unexpected BIOS operation during affine resource load')

        u.hook_add(UC_HOOK_INTR, bios)
        for repeat in range(2):
            u.reg_write(UC_ARM_REG_R0, 440)
            u.reg_write(UC_ARM_REG_SP, 0x03007e00)
            u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
            u.emu_start(0x08051f69, 0x0203fff0, count=200000)
            if u.reg_read(UC_ARM_REG_PC) != 0x0203fff0 or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
                raise ValueError('Original affine loader did not return cleanly')
            if bytes(u.mem_read(0x06008000, 15360)) != expected:
                raise ValueError('Real loader did not supply the exact font pixels')
            if bytes(u.mem_read(0x06000000, 0x8000)) != b'\x5a' * 0x8000 or bytes(u.mem_read(0x0600bc00, 0xc400)) != b'\x5a' * 0xc400:
                raise ValueError('Font load damaged adjacent VRAM')
            palette = b'\x3c' * 0x140 + old[0xd882a8:0xd882e8] + b'\x3c' * (1024 - 0x180)
            if bytes(u.mem_read(0x05000000, 1024)) != palette:
                raise ValueError('Palette load changed unrelated colors')
            if bytes(u.mem_read(0x02010000, 320)) != bytes(256) + b'\xcc' * 64:
                raise ValueError('Original affine map clearing or boundary differs')
            if bytes(u.mem_read(0x020000f8, 12)) != struct.pack('<I4H', 0x08d882ec, 0, 15, 9, 6):
                raise ValueError('Original affine map/size/frame metadata changed')
        loads.append({'image': name, 'load_count': 2, 'bios_events': events})
    report = {'status': 'PASS', 'rom_sha256': hashlib.sha256(rom).hexdigest(), 'localized_symbols': 8,
              'original_affine_font_bytes': 15360, 'resource_loads': loads,
              'scope': 'Original resource 440 table selection, bank getter, decompression dispatch and map initialization execute twice on each image. BIOS RLEVRAM and palette CpuSet are modeled with exact source/output bounds. Eight intended symbol tiles only; all other atlas pixels, palette, metadata and neighboring memory preserved. Normal gameplay and other element renderers remain separate.'}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
