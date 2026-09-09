"""Execute the complete original inspection producer and new affine renderer.

Only the final DMA transfer is modeled. No guest save or gameplay state is
modified by this isolated CPU fixture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

from text_codec import encode
from verify_small_consumer import Fixture

ROOT = Path(__file__).resolve().parents[1]
MAP = 0x02010000
ACTOR = 0x02002000


def unpack_rle(rom, at):
    header = int.from_bytes(rom[at:at + 4], 'little')
    if header & 255 != 0x30:
        raise ValueError('Expected BIOS RLE font resource')
    wanted = header >> 8
    cursor = at + 4
    result = bytearray()
    while len(result) < wanted:
        control = rom[cursor]
        cursor += 1
        if control & 128:
            result.extend([rom[cursor]] * ((control & 127) + 3))
            cursor += 1
        else:
            count = control + 1
            result.extend(rom[cursor:cursor + count])
            cursor += count
    if len(result) != wanted:
        raise ValueError('Font resource exceeds declared size')
    return bytes(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rom, old = args.rom.read_bytes(), args.legacy.read_bytes()
    profile = json.loads((ROOT / 'source/inspect_eye_profile.json').read_text('utf-8'))
    names = json.loads((ROOT / 'translations/items-monsters.json').read_text('utf-8'))['groups']['monster']
    glyphs = json.loads((ROOT / 'fonts/dalmoori-wansung.json').read_text('utf-8'))
    labels = {r['id']: r['text'] for r in json.loads((ROOT / 'translations/inspect_eye.json').read_text('utf-8'))['records']}
    changed = set(range(0x16a48, 0x16a50))
    for row in profile['records']:
        off = int(row['pointer_offset'], 0)
        changed.update(range(off, off + 4))
        ptr = struct.unpack_from('<I', rom, off)[0] - 0x08000000
        raw = encode(labels[row['id']]) + b'\0'
        if not 0x1110000 <= ptr < 0x1111000 or rom[ptr:ptr + len(raw)] != raw:
            raise ValueError('Inspection label bytes or allocation differ')
    for guard in profile['guards']:
        off = int(guard['offset'], 0)
        for i, value in enumerate(bytes.fromhex(guard['hex'])):
            if off + i not in changed and rom[off + i] != value:
                raise ValueError('Original inspection behavior changed')
    for resource in profile['protected_resources']:
        off = int(resource['offset'], 0)
        if rom[off:off + resource['size']] != old[off:off + resource['size']]:
            raise ValueError('Original inspection graphics changed')
    font_at = 0xd4524c + struct.unpack_from('<I', rom, 0xd456b8)[0]
    atlas = unpack_rle(rom, font_at)
    if len(atlas) != 240 * 64 or rom[0xd882e8:0xd882ec] != bytes([15, 9, 6, 0]):
        raise ValueError('Inspection spare-tile geometry differs')
    source_map = rom[0xd882ec:0xd882ec + 15 * 9 * 6]
    if max(source_map) >= 240:
        raise ValueError('Original resource already uses a reserved Hangul tile')
    initial = bytearray(256)
    for y in range(9):
        initial[y * 16:y * 16 + 15] = source_map[y * 15:y * 15 + 15]
    for n, row in enumerate(names):
        at = 0x1021ac + n * 56
        ptr = struct.unpack_from('<I', rom, at)[0] - 0x08000000
        if rom[ptr:rom.index(0, ptr)] != encode(row['compact']):
            raise ValueError('Inspection title does not match selected monster record')
        if rom[at + 4:at + 56] != old[at + 4:at + 56]:
            raise ValueError('Monster behavior, HP or attribute metadata changed')

    f = Fixture(rom, 0)
    u = f.uc
    u.mem_write(0x020000f8, struct.pack('<I', 0x08d882ec))
    u.mem_write(0x02000104, struct.pack('<I', MAP))
    u.mem_write(0x06008000, atlas)
    u.mem_write(0x0600bc00, b'\x5a' * 0x400)
    transfers = []
    vram_writes = []

    def dma(uc, address, size, data):
        # Original 51F04 queues exactly 64 words from this buffer to F000.
        uc.mem_write(0x0600f000, bytes(uc.mem_read(MAP, 256)))
        transfers.append(256)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def record_write(uc, access, address, size, value, data):
        if not 0x0600bc00 <= address or address + size > 0x0600bfc0 or size != 2:
            raise ValueError(f'Inspection writes outside its 15 spare tiles: {address:08X}, {size}')
        vram_writes.append((address, size))

    u.hook_add(UC_HOOK_CODE, dma, begin=0x08051f04, end=0x08051f04)
    u.hook_add(UC_HOOK_MEM_WRITE, record_write, begin=0x06000000, end=0x06017fff)

    def old_tile(value, hiragana=False):
        if hiragana:
            value += 64
        offset = struct.unpack_from('<h', rom, 0x7c1938 + value * 2)[0]
        return rom[0xd882ec + offset]

    cases = [(n, 580, 580, 8, bytes([0x99] * 7 + [0xc0])) for n in range(212)]
    cases += [(19, 1, 32767, element, bytes([0x80] * 8)) for element in range(9)]
    for attribute in range(8):
        for value in [0, 1, 0x7f, 0x80, 0x81, 0x99, 0xff]:
            rates = bytearray([0x80] * 8)
            rates[attribute] = value
            cases.append((136, 580, 580, 8, bytes(rates)))
    cases += [(n, 0, 32767, 0, bytes([value] * 8)) for n, value in [(19, 0), (136, 0x80), (0, 255)]]
    glyph_count = 0
    max_title = 0
    # F000..F0FF is the destination of the original map DMA, checked below.
    # Everything adjacent to the glyph allocation except that map is protected.
    protected_ranges = [(0x0600bfc0, 0x40), (0x0600c000, 0x3000), (0x0600f100, 0x700)]
    protected_vram = [(at, bytes(u.mem_read(at, size))) for at, size in protected_ranges]
    for n, hp, maximum, element, rates in cases:
        actor = bytearray(b'\xa5' * 0x200)
        actor[0x102] = n
        struct.pack_into('<hh', actor, 0x106, hp, maximum)
        actor[0x139] = element
        actor[0x13a:0x142] = rates
        u.mem_write(ACTOR, bytes(actor))
        u.mem_write(MAP, bytes(initial) + b'\xcc' * 64)
        keep = {reg: 0x14141414 + i * 0x01010101 for i, reg in enumerate(
            [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11])}
        for reg, value in keep.items():
            u.reg_write(reg, value)
        u.reg_write(UC_ARM_REG_R0, ACTOR)
        u.reg_write(UC_ARM_REG_SP, 0x03007e00)
        u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
        u.emu_start(0x0801697d, 0x0203fff0, count=1000000)
        if u.reg_read(UC_ARM_REG_PC) != 0x0203fff0 or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
            raise ValueError('Inspection did not return with balanced stack')
        if any(u.reg_read(reg) != value for reg, value in keep.items()):
            raise ValueError('Inspection clobbered a callee-saved register')
        if bytes(u.mem_read(ACTOR, 0x200)) != actor:
            raise ValueError('Inspection changed actor state')
        wanted = bytearray(initial)

        def text_at(x, y, text):
            nonlocal glyph_count
            for ch in text:
                if ch in glyphs:
                    tile = ({0: 0xef, 3: 0xf8, 5: 0xfa, 7: 0xfc}[y]) + x
                    pixels = bytes(0xaf if p == '#' else 0xa1 for line in glyphs[ch] for p in line)
                    if bytes(u.mem_read(0x06008000 + tile * 64, 64)) != pixels:
                        raise ValueError(f'Inspection Hangul pixels differ: {n}, {ch}, ({x},{y})')
                    glyph_count += 1
                else:
                    raw = encode(ch)
                    if len(raw) != 1:
                        raise ValueError('Unmodeled original inspection character')
                    tile = old_tile(raw[0])
                wanted[y * 16 + x] = tile
                x += 1

        text_at(1, 0, names[n]['compact'])
        text_at(1, 1, f'HP{hp:5d}/{maximum:5d}')
        for identity, y in [('attack', 3), ('resistance', 5), ('weakness', 7)]:
            text_at(1, y, labels[identity])
        if element != 8:
            wanted[3 * 16 + 7] = old_tile(0x80 + element)
        for y, indices in [(5, [i for i, rate in enumerate(rates) if rate < 128]),
                           (7, [i for i, rate in enumerate(rates) if rate > 128])]:
            for j, attribute in enumerate(indices):
                wanted[y * 16 + 5 + j] = old_tile(0x80 + attribute)
        if bytes(u.mem_read(MAP, 256)) != wanted:
            got = bytes(u.mem_read(MAP, 256))
            diff = [(i, a, b) for i, (a, b) in enumerate(zip(got, wanted)) if a != b]
            raise ValueError(f'Inspection map/selection differs: {n}, {diff[:20]}')
        if bytes(u.mem_read(0x0600f000, 256)) != wanted or bytes(u.mem_read(MAP + 256, 64)) != b'\xcc' * 64:
            raise ValueError('Inspection map DMA or extent differs')
        if bytes(u.mem_read(0x06008000, len(atlas))) != atlas or any(
                bytes(u.mem_read(at, len(data))) != data for at, data in protected_vram):
            raise ValueError('Inspection damaged original atlas or adjacent VRAM')
        max_title = max(max_title, len(names[n]['compact']))
    report = {'status': 'PASS', 'rom_sha256': hashlib.sha256(rom).hexdigest(),
              'complete_producer_cases': len(cases), 'monster_titles': 212, 'label_fields': 3,
              'hangul_glyph_position_checks': glyph_count, 'maximum_title_cells': max_title,
              'vram_halfword_writes': len(vram_writes), 'modeled_dma_transfers': len(transfers),
              'reserved_tile_indices': [240, 254], 'persistent_ram_bytes': 0,
              'actor_and_monster_metadata_preserved': True,
              'scope': 'Original monster/HP/element/resistance producer and formatter execute. New affine Hangul pixels, complete byte map, borders, repeated reuse, signed resistance boundaries, all eight element symbols and no-attribute ID 8 verified. The 256-byte final DMA is modeled. Normal gameplay and resource lifetime are separate.'}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
