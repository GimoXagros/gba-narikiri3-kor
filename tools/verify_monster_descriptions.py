"""Execute real monster-library description helper and unlocked caller segment."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R5, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

from monster_descriptions import BASE, COUNT, STRIDE, FIELD, START, END, validate_sources, source_string
from text_codec import encode
from verify_small_consumer import Fixture
from verify_skill_text import glyphs
from large_pixel_reference import color_lut, expected_buffer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--j', type=Path, required=True)
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--render-selected-dir', type=Path)
    args = parser.parse_args()
    rom, japanese, legacy = args.rom.read_bytes(), args.j.read_bytes(), args.legacy.read_bytes()
    profile, catalog = validate_sources(japanese, legacy)
    selected = {r['id']: r for r in catalog['records']}
    for guard in profile['guards']:
        at, raw = int(guard['offset'], 0), bytes.fromhex(guard['hex'])
        if rom[at:at + len(raw)] != raw:
            raise ValueError('Original monster-description consumer changed')
    descriptions = []
    for i in range(COUNT):
        at = BASE + i * STRIDE
        if rom[at:at + FIELD] != legacy[at:at + FIELD]:
            raise ValueError('Monster library non-pointer metadata changed')
        original_ptr = struct.unpack_from('<I', legacy, at + FIELD)[0]
        original = source_string(legacy, original_ptr)
        original_at = original_ptr - 0x08000000
        if rom[original_at:original_at + len(original)] != original:
            raise ValueError('Original shared/interior description bytes changed')
        pointer = struct.unpack_from('<I', rom, at + FIELD)[0]
        raw = source_string(rom, pointer)[:-1]
        if i in selected:
            offset = pointer - 0x08000000
            if not 0x1000000 + START <= offset or offset + len(raw) + 1 > 0x1000000 + END:
                raise ValueError('Monster description pointer is outside its allocation')
            if raw != encode(selected[i]['text']):
                raise ValueError('Monster description relocated content differs')
        elif pointer != original_ptr:
            raise ValueError('Unselected monster description pointer changed')
        lines = [glyphs(line) for line in raw.split(b'\n')]
        if not 1 <= len(lines) <= 2 or any(len(line) > 18 for line in lines):
            raise ValueError('Monster description exceeds two-row display geometry')
        positions = [(x, y, slot) for y, line in enumerate(lines) for x, slot in enumerate(line)]
        descriptions.append((pointer, positions))
    cases, positions_count, fill_count = 0, 0, 0
    renders = {}
    for mode in (0, 1):
        fixture = Fixture(rom, mode)
        u = fixture.uc
        # Run the game's original unlock getter against isolated all-set flags.
        u.mem_write(0x02001d68, struct.pack('<I', 0x02009000))
        u.mem_write(0x02009000, b'\xff' * 400)
        drawn, accessed = [], []

        def observe(uc, address, size, data):
            nonlocal fill_count
            if address == 0x08001414:
                drawn.append(tuple(uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
            elif address == 0x08001660:
                accessed.append(uc.reg_read(UC_ARM_REG_R0))
            elif address == 0x080dd428:
                source, dest, control = (uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
                if (dest, control) != (0x03000560, 0x050003c0):
                    raise ValueError('Unexpected description BIOS fill transfer')
                uc.mem_write(dest, bytes(uc.mem_read(source, 4)) * 0x3c0)
                fill_count += 1
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

        for address in (0x08001414, 0x08001660, 0x080dd428):
            u.hook_add(UC_HOOK_CODE, observe, begin=address, end=address)
        paths = [('helper', 0x080ce12c, 0x0203fff0),
                 ('unlocked-gallery-caller', 0x080cd894, 0x080cd8aa)]
        for ident, (pointer, wanted) in enumerate(descriptions):
            want_pixels = expected_buffer(rom, wanted, mode)
            buffers = []
            for label, entry, stop in paths:
                u.mem_write(0x03000040, bytes([0, 0, 18, 2, 0, 0, 0, 13, 1, 28, 15, 4, 0, 0, 0, 0]))
                u.mem_write(0x0300055c, b'\xa5' * 4)
                u.mem_write(0x03001464, color_lut(mode))
                u.mem_write(0x03000560, expected_buffer(rom, [], mode))
                for reg, value in [(UC_ARM_REG_R0, ident), (UC_ARM_REG_R5, ident),
                                   (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x0203fff1)]:
                    u.reg_write(reg, value)
                drawn.clear()
                accessed.clear()
                # The first original VBlank helper precedes the flag check;
                # enter after it because isolated fixtures do not drive LCD time.
                start = 0x080cd898 if label == 'unlocked-gallery-caller' else entry
                u.emu_start(start | 1, stop, count=5000000)
                if u.reg_read(UC_ARM_REG_PC) != stop or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
                    raise ValueError('Monster description return/stack differs')
                if accessed != [pointer]:
                    raise ValueError(f'Monster {ident} real consumer accessed the wrong pointer: {accessed}')
                if drawn != wanted:
                    raise ValueError(f'Monster {ident}, {label}, mode {mode} glyph placement differs: {drawn} != {wanted}')
                if bytes(u.mem_read(0x0300055c, 4)) != b'\xa5' * 4 or bytes(u.mem_read(0x03001464, 4)) != color_lut(mode):
                    raise ValueError('Monster description font buffer boundary changed')
                actual = bytes(u.mem_read(0x03000560, 0xf00))
                if actual != want_pixels:
                    raise ValueError(f'Monster {ident}, {label}, mode {mode} pixels differ from original font bits')
                buffers.append(actual)
                cases += 1
                positions_count += len(drawn)
            if buffers[0] != buffers[1]:
                raise ValueError('Direct and original gallery caller disagree')
            if mode == 0 and ident in selected:
                renders[ident] = buffers[0]
    if args.render_selected_dir:
        from PIL import Image, ImageDraw
        args.render_selected_dir.mkdir(parents=True, exist_ok=False)
        cards = []
        for ident, buffer in renders.items():
            card = Image.new('RGB', (240, 44), '#eff1fc')
            ImageDraw.Draw(card).text((2, 0), f'MONSTER {ident:03d} - CPU FIXTURE', fill='black')
            for y in range(32):
                for x in range(240):
                    at = ((y // 8) * 30 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                    if (buffer[at] >> (4 * (x % 2))) & 15:
                        card.putpixel((x, y + 12), (0, 0, 0))
            cards.append(card)
        for start in range(0, len(cards), 7):
            chunk = cards[start:start + 7]
            page = Image.new('RGB', (240, len(chunk) * 48), 'white')
            for i, card in enumerate(chunk):
                page.paste(card, (0, i * 48))
            page.resize((page.width * 3, page.height * 3), Image.Resampling.NEAREST).save(args.render_selected_dir / f'page-{start // 7 + 1:02d}.png')
    result = {'status': 'PASS', 'rom_sha256': hashlib.sha256(rom).hexdigest(),
        'typed_monster_library_records': COUNT, 'selected_description_repairs': len(selected),
        'original_description_helper_cases': COUNT * 2, 'original_unlocked_caller_cases': COUNT * 2,
        'total_consumer_cases': cases, 'large_glyph_position_checks': positions_count,
        'bios_fill_substitutions': fill_count, 'non_pointer_metadata_preserved': True,
        'original_shared_strings_preserved': True, 'complete_pixel_buffers_match_original_font_bits': True,
        'natural_gallery_entry': 'not_run',
        'scope': 'All 212 description records, original 0x080CE12C helper and unlocked 0x080CD898..0x080CD8AA caller segment, both font modes. Real original unlock getter and pointer loads execute; BIOS fixed fill is modeled. Selected text fits two 18-cell rows. No whole-menu interaction, discovery progression or natural gallery entry claim.'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
