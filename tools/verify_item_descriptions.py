"""Run all typed item descriptions through their five original display callers."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from verify_small_consumer import Fixture
from verify_skill_text import glyphs
from text_codec import encode

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--render-selected-dir', type=Path)
    args = parser.parse_args()
    rom, old = args.rom.read_bytes(), args.legacy.read_bytes()
    profile = json.loads((ROOT / 'source/item_description_profile.json').read_text('utf-8'))
    catalog = json.loads((ROOT / 'translations/item_descriptions.json').read_text('utf-8'))
    selected = {r['id']: r['text'] for r in catalog['records']}
    for guard in profile['guards']:
        at = int(guard['offset'], 0)
        raw = bytes.fromhex(guard['hex'])
        if rom[at:at + len(raw)] != raw:
            raise ValueError('Original item-description code differs')
    descriptions = []
    for ident in range(123):
        at = 0x105758 + ident * 24
        source_record = profile['records'][ident]
        source = int(source_record['pointer'], 0) - 0x08000000
        source_end = old.index(0, source) + 1
        if source_record['id'] != ident or hashlib.sha256(old[source:source_end]).hexdigest() != source_record['legacy_description_sha256'] or rom[source:source_end] != old[source:source_end]:
            raise ValueError('Original item description source bytes changed')
        if rom[at + 8:at + 24] != old[at + 8:at + 24]:
            raise ValueError('Item category, effects, costs or recipe metadata changed')
        ptr = struct.unpack_from('<I', rom, at + 4)[0]
        off = ptr - 0x08000000
        raw = rom[off:rom.index(0, off)]
        if ident in selected:
            if not 0x1120000 <= off < 0x1130000 or raw != encode(selected[ident]):
                raise ValueError('Selected item description differs')
        elif rom[at + 4:at + 8] != old[at + 4:at + 8]:
            raise ValueError('Unselected item description pointer changed')
        lines = [glyphs(line) for line in raw.split(b'\n')]
        if not 1 <= len(lines) <= 2 or max(map(len, lines)) > 18:
            raise ValueError('Item description exceeds original two-line window')
        descriptions.append((ptr, [(x, y, slot) for y, line in enumerate(lines) for x, slot in enumerate(line)]))
    cases, positions, getters, fills = 0, 0, 0, []
    rendered = {}
    paths = [('selection', 0x080cabb4, 0x080cabce),
             ('alternate-selection', 0x080cb18e, 0x080cb1a8),
             ('after-validation', 0x080cb21e, 0x080cb22e),
             ('direct-description', 0x080d1468, 0x0203fff0),
             ('formatted-description', 0x080d9328, 0x0203fff0)]
    for mode in (0, 1):
        fixture = Fixture(rom, mode)
        u = fixture.uc
        u.mem_write(0x02003380, struct.pack('<I', 0x02020000))
        u.mem_write(0x02020680, struct.pack('<I', 0x02021000))
        drawn = []

        def observe(uc, address, size, data):
            if address == 0x08001414:
                drawn.append(tuple(uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
            elif address == 0x080dd428:
                source, dest, control = (uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
                if (dest, control) != (0x03000560, 0x050003c0):
                    raise ValueError('Unexpected item description BIOS transfer')
                uc.mem_write(dest, bytes(uc.mem_read(source, 4)) * 0x3c0)
                fills.append((dest, 0xf00))
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

        u.hook_add(UC_HOOK_CODE, observe, begin=0x08001414, end=0x08001414)
        u.hook_add(UC_HOOK_CODE, observe, begin=0x080dd428, end=0x080dd428)

        def run(pc, stop=0x0203fff0):
            u.reg_write(UC_ARM_REG_SP, 0x03007e00)
            u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
            u.emu_start(pc | 1, stop, count=5000000)
            if u.reg_read(UC_ARM_REG_PC) != stop or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
                raise ValueError('Item description return/stack differs')

        for ident, (ptr, wanted) in enumerate(descriptions):
            u.reg_write(UC_ARM_REG_R0, ident)
            run(0x08006600)
            if u.reg_read(UC_ARM_REG_R0) != ptr:
                raise ValueError('Original item description getter differs')
            getters += 1
            buffers = []
            background = 11 if mode else 0
            # 03001464 is the live 2-bit-to-two-nibble expansion table,
            # not unused guard RAM. These are the original palette mappings.
            color_lut = bytes([background * 17, background * 16 + 15, 240 + background, 255])
            expected_buffer = bytearray([background * 17] * 0xf00)
            for cell_x, cell_y, slot in wanted:
                font_rows = struct.unpack_from('<16H', rom, 0xddcc4 + slot * 32)
                for row_y, bits in enumerate(font_rows):
                    for col_x in range(12):
                        x, y = cell_x * 12 + col_x, cell_y * 16 + row_y
                        at = ((y // 8) * 30 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                        shift = 4 * (x % 2)
                        color = 15 if bits & (1 << col_x) else background
                        expected_buffer[at] = (expected_buffer[at] & ~(15 << shift)) | (color << shift)
            for label, start, stop in paths:
                u.mem_write(0x03000040, bytes([0, 0, 18, 2, 0, 0, 0, 13, 1, 28, 15, 4, 0, 0, 0, 0]))
                u.mem_write(0x03000560, bytes(0xf00))
                u.mem_write(0x0300055c, b'\xa5' * 4)
                u.mem_write(0x03001464, color_lut)
                u.mem_write(0x02021000, bytes([ident]))
                u.reg_write(UC_ARM_REG_R0, 0)
                u.reg_write(UC_ARM_REG_R4, 0)
                u.reg_write(UC_ARM_REG_R5, ident if label == 'after-validation' else 0x02003380)
                drawn.clear()
                run(start, stop)
                if drawn != wanted:
                    raise ValueError(f'Item {ident}, {label}, mode {mode} glyph/position differs: {drawn} != {wanted}')
                if bytes(u.mem_read(0x0300055c, 4)) != b'\xa5' * 4 or bytes(u.mem_read(0x03001464, 4)) != color_lut:
                    raise ValueError('Item description font buffer boundary changed')
                buffers.append(bytes(u.mem_read(0x03000560, 0xf00)))
                if buffers[-1] != expected_buffer:
                    raise ValueError(f'Item {ident}, {label}, mode {mode} actual pixels differ from original font bits')
                cases += 1
                positions += len(drawn)
            if any(buffer != buffers[0] for buffer in buffers[1:]):
                raise ValueError(f'Item {ident} has different pixels across original callers')
            if mode == 0 and ident in selected:
                rendered[ident] = buffers[0]
    if args.render_selected_dir:
        from PIL import Image, ImageDraw
        args.render_selected_dir.mkdir(parents=True, exist_ok=False)
        cards = []
        for ident, buffer in rendered.items():
            card = Image.new('RGB', (240, 44), '#eff1fc')
            ImageDraw.Draw(card).text((2, 0), f'ITEM {ident:03d} - CPU FIXTURE', fill='black')
            for y in range(32):
                for x in range(240):
                    at = ((y // 8) * 30 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                    nibble = (buffer[at] >> (4 * (x % 2))) & 15
                    if nibble:
                        card.putpixel((x, y + 12), (0, 0, 0))
            cards.append(card)
        for start in range(0, len(cards), 7):
            page = Image.new('RGB', (240, 48 * len(cards[start:start + 7])), 'white')
            for n, card in enumerate(cards[start:start + 7]):
                page.paste(card, (0, n * 48))
            page.resize((page.width * 3, page.height * 3), Image.Resampling.NEAREST).save(args.render_selected_dir / f'page-{start // 7 + 1:02d}.png')
    result = {'status': 'PASS', 'rom_sha256': hashlib.sha256(rom).hexdigest(),
              'typed_item_records': 123, 'selected_description_repairs': len(selected),
              'original_getter_cases': getters, 'original_description_caller_cases': cases,
              'large_glyph_position_checks': positions, 'bios_fill_substitutions': len(fills),
              'item_metadata_preserved': True, 'complete_pixel_buffers_match_original_font_bits': True,
              'scope': 'All 123 typed descriptions, five original getter/formatter/large-pixel caller paths, both font modes. Every complete pixel buffer independently matches original 12x16 font bits, with real palette expansion values and two-line boundaries. Only fixed BIOS font-buffer fills are modeled; inventory selection and zero character delay are isolated CPU fixtures. Normal item acquisition and full-game runtime are separate.'}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
