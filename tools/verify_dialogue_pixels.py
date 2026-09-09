"""Selected typed dialogue: original expansion, formatting, scrolling and pixels.

The isolated fixture supplies BIOS CpuSet, VBlank/key input and sound completion.
It never writes a runtime save or imports a state into a game session.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R9, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from dialogue_tokens import expand_expected, units
from large_pixel_reference import color_lut, expected_buffer
from text_codec import encode
from verify_dialogue_resource import Expander
from verify_skill_text import glyphs

ROOT = Path(__file__).resolve().parents[1]


def expected_events(raw):
    """Independent 18x2 cursor model; newline and automatic wrap scroll one row."""
    events, cells, x, y = [], list(units(raw)), 0, 0
    i = 0
    while i < len(cells):
        char = cells[i][1]
        if char == b'%':
            if i + 1 == len(cells) or cells[i + 1][1] not in (b'k', b'l'):
                raise ValueError('Unmodeled selected dialogue format control')
            command = cells[i + 1][1]
            events.append(('wait' if command == b'k' else 'clear',))
            if command == b'l': x, y = 0, 0
            i += 2
            continue
        if char == b'\n':
            x = 18
        if x >= 18:
            x, y = 0, y + 1
            if y >= 2:
                events.append(('scroll',))
                y = 1
        if char != b'\n':
            # Original ASCII conversion table FFE80, selected by 741D80
            # in 4D90: these six slots differ from Unicode full width.
            special = {b'"': '”', b"'": '’', b'\\': '￥',
                       b']': '」', b'`': '‘', b'~': '￣'}
            slot, = glyphs(encode(special[char]) if char in special else char)
            events.append(('glyph', x, y, slot))
            x += 1
        i += 1
    return events


class PixelFixture:
    def __init__(self, rom, mode):
        self.rom, self.mode = rom, mode
        self.expander = Expander(rom, mode)
        self.u = u = self.expander.u
        self.events, self.positions, self.snapshots = [], [], []
        self.bios_calls = self.vblanks = self.sounds = 0
        for address in (0x08001414, 0x080010d8, 0x0800103c, 0x08002320,
                        0x080dd428, 0x080004ec, 0x080dbecc):
            u.hook_add(UC_HOOK_CODE, self.observe, begin=address, end=address)

    def compare_pixels(self, snapshot=False):
        actual = bytes(self.u.mem_read(0x03000560, 0xf00))
        if actual != expected_buffer(self.rom, self.positions, self.mode):
            raise ValueError('Dialogue pixels differ from original font bits')
        if snapshot:
            self.snapshots.append(actual)
        if bytes(self.u.mem_read(0x0300055c, 4)) != b'\xa5'*4 or bytes(self.u.mem_read(0x03001464, 4)) != color_lut(self.mode):
            raise ValueError('Dialogue pixel-buffer boundary or palette changed')

    def observe(self, u, address, size, data):
        if address == 0x08001414:
            values = tuple(u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            self.events.append(('glyph', *values))
            if not 0 <= values[0] < 18 or not 0 <= values[1] < 2:
                raise ValueError('Dialogue glyph outside established window')
            self.positions = [p for p in self.positions if p[:2] != values[:2]] + [values]
        elif address in (0x080010d8, 0x0800103c, 0x08002320):
            self.compare_pixels(snapshot=True)
            if address == 0x080010d8:
                if u.reg_read(UC_ARM_REG_R0) != 8:
                    raise ValueError('Unexpected dialogue scroll speed')
                self.events.append(('scroll',))
                self.positions = [(x, 0, slot) for x, y, slot in self.positions if y == 1]
            elif address == 0x0800103c:
                self.events.append(('clear',))
                self.positions = []
            else:
                self.events.append(('wait',))
        elif address == 0x080dd428:
            src, dst, control = (u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            allowed = {(0x03000560, 0x050003c0), (0x03000560, 0x040002d0),
                       (0x030010a0, 0x050000f0)}
            if (dst, control) not in allowed:
                raise ValueError(f'Unexpected dialogue BIOS transfer {src:x}, {dst:x}, {control:x}')
            size = (control & 0x1fffff) * 4
            if control & 0x1000000:
                value = bytes(u.mem_read(src, 4)) * (size // 4)
            else:
                if src != 0x03000920:
                    raise ValueError('Unexpected dialogue scroll source')
                value = bytes(u.mem_read(src, size))
            u.mem_write(dst, value)
            self.bios_calls += 1
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        elif address == 0x080004ec:
            # Complete one VBlank and provide the A edge requested by 2320.
            u.mem_write(0x030033f8, b'\x01\x00')
            self.vblanks += 1
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        elif address == 0x080dbecc:
            self.sounds += 1
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def run(self, ptr, raw, names):
        expanded = expand_expected(raw, names)
        self.expander.names(names)
        self.expander.run(ptr, expanded)
        u = self.u
        u.mem_write(0x03000040, bytes([0, 0, 18, 2, 0, 0, 0, 13, 1, 28, 15, 4, 0, 0, 0, 0]))
        u.mem_write(0x03000560, expected_buffer(self.rom, [], self.mode))
        u.mem_write(0x0300055c, b'\xa5'*4)
        u.mem_write(0x03001464, color_lut(self.mode))
        self.events, self.positions, self.snapshots = [], [], []
        u.reg_write(UC_ARM_REG_R9, self.expander.buf)
        u.reg_write(UC_ARM_REG_SP, 0x03007e00)
        u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
        # Actual VM dialogue caller after its original name-expansion path.
        u.emu_start(0x080c762d, 0x080c7632, count=10000000)
        if u.reg_read(UC_ARM_REG_PC) != 0x080c7632 or u.reg_read(UC_ARM_REG_SP) != 0x03007e00:
            raise ValueError('Dialogue formatter caller return/stack differs')
        want = expected_events(expanded)
        if self.events != want:
            raise ValueError(f'Dialogue glyph/control positions differ: {self.events!r} != {want!r}')
        self.compare_pixels(snapshot=True)
        return len([e for e in self.events if e[0] == 'glyph'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--legacy', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--render-records', nargs='*', type=lambda s: int(s, 0))
    p.add_argument('--render-dir', type=Path)
    a = p.parse_args()
    rom, old = a.rom.read_bytes(), a.legacy.read_bytes()
    if hashlib.sha256(old).hexdigest() != '8440f3e3db46c474c81cf84098798f07ab91aa13d48431c523c309a0af363010':
        raise ValueError('Unexpected legacy reference')
    for start, end in ((0xc762c, 0xc7632), (0xea8, 0x16e8), (0x2320, 0x23f0), (0x25cc, 0x2860), (0xffe80, 0xfff3e), (0x741d80, 0x741d84)):
        if rom[start:end] != old[start:end]:
            raise ValueError('Original dialogue formatter/display code changed')
    rows = json.loads((ROOT/'source/dialogue_fixes.json').read_text('utf-8'))['records']
    target = {r['id']: r['text'] for r in json.loads((ROOT/'translations/dialogue_fixes.json').read_text('utf-8'))['records']}
    samples = [('default', ('훌리오', '캐로', '드림', '크라토스', '프레세아')),
               ('maximum', ('가나다라마',)*5),
               ('mixed', ('가A나B다', 'A캐B로C', 'AB드림C', 'A크라B스', 'A프레B아'))]
    cases = pixels = snapshots = bios = vblanks = sounds = 0
    cards = []
    for mode in (0, 1):
        fixture = PixelFixture(rom, mode)
        for label, values in samples:
            names = {k: encode(v) for k, v in zip((b'@B', b'@G', b'@D', b'@0', b'@1'), values)}
            for row in rows:
                off = int(row['record_offset'], 0)
                ptr = struct.unpack_from('<I', rom, off+4)[0]
                start = ptr-0x08000000
                raw = rom[start:rom.index(0, start)]
                if raw != encode(target[row['id']]):
                    raise ValueError('Relocated dialogue differs from adopted text')
                try:
                    pixels += fixture.run(ptr, raw, names)
                except Exception as error:
                    raise ValueError(f"{row['id']} / {label} / mode {mode}: {error}") from error
                cases += 1
                snapshots += len(fixture.snapshots)
                if mode == 0 and label == 'default' and off in (a.render_records or []):
                    for n, buf in enumerate(fixture.snapshots):
                        cards.append((f'{off:06X} VIEW {n+1} - CPU FIXTURE', buf))
        bios += fixture.bios_calls
        vblanks += fixture.vblanks
        sounds += fixture.sounds
    if a.render_dir:
        from PIL import Image, ImageDraw
        a.render_dir.mkdir(parents=True, exist_ok=False)
        for start in range(0, len(cards), 7):
            batch = cards[start:start+7]
            page = Image.new('RGB', (240, 48*len(batch)), 'white')
            draw = ImageDraw.Draw(page)
            for n, (label, buf) in enumerate(batch):
                draw.text((2, n*48), label, fill='black')
                for y in range(32):
                    for x in range(240):
                        at = ((y//8)*30+x//8)*32+(y%8)*4+(x%8)//2
                        if (buf[at] >> (4*(x%2))) & 15:
                            page.putpixel((x, n*48+12+y), (0, 0, 0))
            page.resize((720, page.height*3), Image.Resampling.NEAREST).save(a.render_dir/f'page-{start//7+1:02d}.png')
    result = {'status': 'PASS', 'rom_sha256': hashlib.sha256(rom).hexdigest(),
              'selected_dialogue_records': len(rows), 'original_expansion_and_display_cases': cases,
              'large_glyph_position_checks': pixels, 'complete_pixel_snapshots': snapshots,
              'bios_transfer_substitutions': bios, 'vblank_input_substitutions': vblanks,
              'sound_substitutions': sounds, 'complete_pixel_buffers_match_original_font_bits': True,
              'scope': 'All selected dialogue operands, three name samples and both background modes. Actual original name expansion and C762C formatter caller, ASCII conversion, line wrapping, scrolling and key-wait code. Independent cursor/events and complete font-buffer pixel reference at every scroll, wait, clear and return. BIOS font transfers, VBlank/A input and sound completion are modeled. Speaker portraits, consecutive scene timing, natural reachability and full-game review are separate.'}
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', 'utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
