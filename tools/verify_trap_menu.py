"""Validate the original five-item trap picker, its pixels and budget rules."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from PIL import Image
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from text_codec import encode
from verify_small_consumer import Fixture

ROOT = Path(__file__).resolve().parents[1]
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)


def call(u, pc, args=(), stack=()):
    for reg, value in zip(REGS, args):
        u.reg_write(reg, value & 0xffffffff)
    u.reg_write(UC_ARM_REG_SP, 0x03007e00)
    u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
    if stack:
        u.mem_write(0x03007e00, struct.pack('<' + 'I' * len(stack), *stack))
    u.emu_start(pc | 1, 0x0203fff0, count=1000000)
    if u.reg_read(UC_ARM_REG_PC) != 0x0203fff0 or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
        raise ValueError('Trap picker did not return with a balanced stack')
    return u.reg_read(UC_ARM_REG_R0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--legacy', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    rom = a.rom.read_bytes()
    legacy = a.legacy.read_bytes()
    profile = json.loads((ROOT / 'source/ui_profile.json').read_text(encoding='utf-8'))
    selected = [r for r in profile['records'] if r['id'].startswith('trap-menu-')]
    catalog = {r['id']: r['text'] for r in json.loads((ROOT / 'translations/ui.json').read_text(encoding='utf-8'))['records']}
    if len(selected) != 5 or rom[0xdd24b8:0xdd24bc] != b'\0' * 4:
        raise ValueError('Trap list count or terminator differs')
    if hashlib.sha256(legacy).hexdigest() != '8440f3e3db46c474c81cf84098798f07ab91aa13d48431c523c309a0af363010':
        raise ValueError('Wrong immutable legacy comparison')
    texts = []
    pointers = []
    for i, row in enumerate(selected):
        edge = int(row['pointer_offset'], 0)
        if edge != 0xdd24a4 + i * 4:
            raise ValueError('Trap item IDs changed order')
        for guard in row['guards']:
            at = int(guard['offset'], 0)
            raw = bytes.fromhex(guard['hex'])
            actual = bytearray(rom[at:at + len(raw)])
            # The reviewed xlsx-580 prompt is a four-byte literal at the end
            # of this otherwise unchanged caller. Its pointer/text is checked
            # separately by verify_review_ui.py.
            if at <= 0xae220 and 0xae224 <= at + len(raw):
                start = 0xae220 - at
                actual[start:start + 4] = raw[start:start + 4]
            if bytes(actual) != raw or legacy[at:at + len(raw)] != raw:
                raise ValueError('Trap original consumer code changed')
        ptr = struct.unpack_from('<I', rom, edge)[0]
        text = catalog[row['id']]
        at = ptr - 0x08000000
        if not 0x1060000 <= at < 0x1070000 or rom[at:rom.index(0, at)] != encode(text) or len(text) > 8:
            raise ValueError('Trap text pointer, bytes or window width differs')
        texts.append(text)
        pointers.append(ptr)
    glyphs = json.loads((ROOT / 'fonts/dalmoori-wansung.json').read_text(encoding='utf-8'))
    outputs = 0
    cursor_cases = 0
    images = []
    for mode in (0, 1):
        f = Fixture(rom, mode)
        base = Fixture(rom, mode)
        u = f.uc
        window = 0x02001000
        call(base.uc, 0x080016e8, (window, 11, 3, 8), (5,))
        expected = bytearray(base.pixels())
        geometry = bytes(base.uc.mem_read(window, 8))
        if geometry != bytes([11, 3, 19, 13 if mode == 0 else 12, 11, 4 if mode == 0 else 3, 1 if mode == 0 else 2, 13]):
            raise ValueError('Original trap window geometry differs')
        call(u, 0x080016e8, (window, 11, 3, 8), (5,))
        visited = []
        formatted = []
        def observe(uc, address, size, _):
            if address == 0x08001da8:
                ptr = uc.reg_read(UC_ARM_REG_R1)
                current = bytes(uc.mem_read(window, 8))
                visited.append((ptr, current[4], current[5]))
                uc.mem_write(0x03001468, b'\xa5' * 256)
            elif address == 0x080044f6:
                ptr = visited[-1][0]
                at = ptr - 0x08000000
                raw = rom[at:rom.index(0, at)]
                want = raw + b'\0' + b'\xa5' * (255 - len(raw))
                if bytes(uc.mem_read(0x03001468, 256)) != want:
                    raise ValueError('Trap formatter content or scratch boundary differs')
                formatted.append(ptr)
            elif address == 0x080dbecc:
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        handle = u.hook_add(UC_HOOK_CODE, observe)
        menu = call(u, 0x0800402c, (window, 0x08dd24a4))
        expected_visits = [(ptr, 11, geometry[5] + i * 2) for i, ptr in enumerate(pointers)]
        if visited != expected_visits or formatted != pointers or menu != 0x03002a50:
            raise ValueError(f'Actual trap list allocation or five text calls differ: mode={mode} menu={menu:#x} visited={visited} wanted={expected_visits} formatted={formatted}')
        if struct.unpack('<HH', u.mem_read(menu + 0x1a, 4)) != (5, 5):
            raise ValueError('Actual trap list population or visible row count differs')
        for i, text in enumerate(texts):
            for column, char in enumerate(text):
                if char == ' ':
                    tile = base.atlas[0x200:0x220]
                else:
                    nibbles = [15 if bit == '#' else base.bg for line in glyphs[char] for bit in line]
                    tile = bytes(nibbles[j] | nibbles[j + 1] << 4 for j in range(0, 64, 2))
                pos = ((geometry[5] + i * 2) * 32 + 11 + column) * 32
                expected[pos:pos + 32] = tile
        if f.pixels() != expected:
            raise ValueError('Whole trap menu pixels differ from independent Hangul bitmaps')
        outputs += len(texts)
        # Original cursor handler, including wrap at both ends; no sprite
        # callbacks are installed by the list constructor in this fixture.
        choice = 0
        for key in [0x80] * 6 + [0x40] * 6:
            choice = (choice + (1 if key == 0x80 else -1)) % 5
            u.mem_write(0x030033fc, struct.pack('<H', key))
            if call(u, 0x08004104, (menu,)) != choice:
                raise ValueError('Original trap cursor index or wrap differs')
            cursor_cases += 1
        u.hook_del(handle)
        # Render a readable diagnostic image from the actual complete map.
        pixels = f.pixels()
        picture = Image.new('RGB', (256, 256))
        rgb = picture.load()
        for cell in range(1024):
            tile = pixels[cell * 32:(cell + 1) * 32]
            for n, value in enumerate(tile):
                for half in (0, 1):
                    level = ((value >> (half * 4)) & 15) * 17
                    rgb[(cell % 32) * 8 + (n * 2 + half) % 8, (cell // 32) * 8 + (n * 2 + half) // 8] = (level, level, level)
        path = a.out.with_name(f'trap-menu-mode-{mode}.png')
        picture.crop((72, 8, 168, 120)).resize((384, 448), Image.Resampling.NEAREST).save(path)
        images.append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    # Execute the original budget loop and its real finish-to--1 mapping.
    # Only text-box output, the interactive chooser and placement action
    # are substituted; item order, remaining-count logic and IDs are original.
    f = Fixture(rom, 0)
    u = f.uc
    choices = []
    placements = []
    remaining = []
    def actions(uc, address, size, _):
        if address in (0x08000ea8, 0x08001660, 0x08001088):
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif address == 0x080ae1d0:
            remaining.append(uc.reg_read(UC_ARM_REG_R0))
        elif address == 0x080aed8c:
            args = [uc.reg_read(r) for r in REGS]
            if args != [0x08dd24a4, 0xffffffff, 3, 8] or struct.unpack('<II', uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 8)) != (5, 0):
                raise ValueError('Actual trap chooser shape/cancel policy differs')
            uc.reg_write(UC_ARM_REG_R0, choices.pop(0))
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif address == 0x080ae050:
            ident, success = placements.pop(0)
            if uc.reg_read(UC_ARM_REG_R0) != ident or uc.reg_read(UC_ARM_REG_R1) != 0x02002000:
                raise ValueError('Trap choice was mapped to the wrong placement ID')
            uc.reg_write(UC_ARM_REG_R0, success)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, actions)
    cases = [([0, 1, 2, 3], [(i, 1) for i in range(4)], [4, 3, 2, 1], 0),
             ([2, 4], [(2, 0)], [4, 4], 4),
             ([1, 4], [(1, 1)], [4, 3], 3),
             ([4], [], [4], 4)]
    for picks, places, counts, result in cases:
        choices[:] = picks
        placements[:] = places
        remaining.clear()
        if call(u, 0x080ae024, (0x02002000, 4)) != result or choices or placements or remaining != counts:
            raise ValueError('Original trap budget or finish behavior changed')
    report = {'status': 'PASS', 'rom_sha256': hashlib.sha256(rom).hexdigest(),
              'translated_trap_entries': 5, 'actual_list_initial_output_calls': outputs,
              'whole_map_pixel_bytes_per_mode': 32768, 'independent_hangul_pixels': True,
              'original_cursor_and_wrap_cases': cursor_cases, 'original_budget_and_finish_cases': len(cases),
              'images': images,
              'scope': 'Original list allocator/renderer/cursor and trap budget/finish logic. Independent Hangul bitmap comparison. Interactive chooser, placement and unrelated output are substituted only in budget cases; not normal access to these later story scenarios.'}
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
