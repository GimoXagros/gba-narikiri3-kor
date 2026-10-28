"""Bounded small-list redraw support; fixed slots, no string/pointer relocation."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source/v13b/small-ui'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bl(at, target):
    delta = target - at - 4
    if delta % 2 or not -(1 << 22) <= delta < (1 << 22):
        raise ValueError('Thumb BL target out of range')
    return struct.pack('<HH', 0xf000 | ((delta >> 12) & 0x7ff),
                       0xf800 | ((delta >> 1) & 0x7ff))


def apply(base, toolchain, out, ui_symbols):
    base = bytes(base)
    if len(base) != 0x1000000:
        raise ValueError('Requires unchanged 16 MiB input')
    toolchain, out = Path(toolchain), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    result = bytearray(base)
    writes, builds = [], {}
    # The runtime fast route admits immutable table pointers only. Certify each
    # accepted byte sequence against the actual encoding before emitting code.
    from text_codec import hangul_map, glyph_index
    fast_names = []
    for ident in range(212):
        pointer = int.from_bytes(base[0x1021ac + ident * 56:0x1021b0 + ident * 56], 'little')
        at = pointer - 0x08000000
        if not 0 <= at < len(base):
            raise ValueError('Monster name pointer outside unchanged ROM')
        codes, length, supported = [], 0, False
        while length <= 62 and at < len(base):
            lead = base[at]
            if lead == 0:
                supported = True
                break
            length += 1
            if lead == 0x20:
                at += 1
                continue
            if not 0x88 <= lead <= 0x95 or at + 1 >= len(base):
                break
            codes.append(int.from_bytes(base[at:at+2], 'big'))
            at += 2
        if supported:
            for code in codes:
                if code not in hangul_map():
                    raise ValueError(f'Unmapped fast-route glyph {ident}: {code:04x}')
                glyph = 0xfbd354 + glyph_index(code) * 8
                if not any(base[glyph:glyph+8]):
                    raise ValueError('Fast-route glyph has no pixels')
            fast_names.append(ident)
    # Both original atlas blank tiles are uniform. Only these two modes are
    # admitted by the existing renderer/context guard.
    for atlas in (0xfbcc4, 0xfdcc4):
        tile = base[atlas+0x200:atlas+0x220]
        if len(set(tile)) != 1 or tile[0] >> 4 != tile[0] & 15:
            raise ValueError('Blank atlas tile is not a uniform repeated nibble')

    def write(at, payload, reason):
        before = bytes(result[at:at + len(payload)])
        result[at:at + len(payload)] = payload
        writes.append(dict(offset=at, bytes=len(payload), before_sha256=sha(before),
                           after_sha256=sha(payload), reason=reason))

    def run(name, args):
        return subprocess.check_output([str(toolchain / ('arm-none-eabi-' + name + '.exe')),
                                        *map(str, args)], text=True)

    defs = dict(UI_CACHE_CONTEXT=ui_symbols['ui_cache_context'] | 1,
                UI_FINAL_COMPOSITE=ui_symbols['ui_final_composite'] | 1,
                SMALL_UI_RENDER=ui_symbols['small_ui_render'] | 1,
                SMALL_NATIVE_FORMAT=ui_symbols['small_native_format'] | 1)
    slots = [('stream', 0xfbbb2c, 0xfbbd40, 'monster_stream'),
             ('tile', 0xfbbd40, 0xfbbe00, 'scoped_tile'),
             ('clear', 0xfbbe00, 0xfbbee0, 'fast_clear'),
             ('rows', 0xfbcb9c, 0xfbcc78, 'rows'),
             ('pin', 0xfbcc78, 0xfbcd2c, 'fast_pin'),
             ('cursor', 0xfbd280, 0xfbd354, 'cursor')]
    for name, at, end, entry in slots:
        obj, elf, binary = [out / (name + suffix) for suffix in ('.o', '.elf', '.bin')]
        args = ['-mcpu=arm7tdmi']
        for key, value in defs.items():
            args += ['--defsym', f'{key}={value}']
        run('as', [*args, SOURCE / ('runtime_' + name + '.s'), '-o', obj])
        run('ld', [f'-Ttext={at + 0x08000000:#x}', '-e', entry, obj, '-o', elf])
        run('objcopy', ['-O', 'binary', elf, binary])
        payload = binary.read_bytes()
        if at + len(payload) > end:
            raise ValueError(f'{name} exceeds reserved range')
        before = base[at:at + len(payload)]
        if name == 'cursor':
            # Tail of the existing, explicitly reserved generic-guard allocation.
            if len(payload) != 132 or sha(before) != 'c37ad5fa465273f0bedf6b273739548cb0caab0150ea8800ae781b194d8cd933':
                raise ValueError('Unrecognized generic-guard tail')
        elif before != b'\xff' * len(payload):
            raise ValueError(f'{name} requires boot-reclaimed FF bytes')
        symbols = {p[2]: int(p[0], 16) for line in run('nm', ['-n', elf]).splitlines()
                   if len(p := line.split()) >= 3}
        builds[name] = dict(address=at, bytes=len(payload), symbols=symbols,
                            source_sha256=sha((SOURCE / ('runtime_' + name + '.s')).read_bytes()))
        write(at, payload, 'bounded ' + name)

    if base[0xfbbfde:0xfbbfe2].hex() != '70263000':
        raise ValueError('Allocator cursor hook mismatch')
    write(0xfbbfde, bl(0x08fbbfde, 0x08fbd280), 'shared-context cursor')
    if sha(base[0xfbd000:0xfbd080]) != 'f78c4225d0f1fb92d62efcb7abcce4565be88c928d66da36c711bfbbc4e72eb5':
        raise ValueError('Original pin helper mismatch')
    write(0xfbd000, bytes.fromhex('004b1847') + struct.pack('<I', 0x08fbcc79),
          'pin helper veneer inside existing allocation')
    if base[0x44c8:0x44cc] != bl(0x080044c8, 0x080017a0):
        raise ValueError('Native clear call mismatch')
    write(0x44c8, bl(0x080044c8, 0x08001d90), 'near bridge for bounded clear')
    if int.from_bytes(base[0x1d98:0x1d9c], 'little') != defs['SMALL_NATIVE_FORMAT']:
        raise ValueError('Scoped variadic veneer mismatch')
    write(0x1d98, struct.pack('<I', builds['clear']['symbols']['clear_gate'] | 1),
          'clear caller gate, other scoped calls retain formatter')

    # These bytes are the unused tail of the explicitly allocated fast-match block,
    # not an arbitrary FF search. Normalize only after recognizing the inherited data.
    at, size = 0xfbcf64, 156
    if sha(base[at:at + size]) != 'b452599d7e4c7d3ab62474850d52c8660b83527839d71f12f84c8abe8e053791':
        raise ValueError('Fast-match allocation tail mismatch')
    write(at, b'\xff' * size, 'reserve numeric guard within fast-match allocation')
    if base[0xfbbee0:0xfbbf70] != b'\xff' * 144:
        raise ValueError('Numeric drawing reservation is not boot-reclaimed')
    if len(result) != len(base):
        raise ValueError('ROM growth forbidden')
    report = dict(input_sha256=sha(base), output_sha256=sha(result), rom_size=len(result),
                  builds=builds, writes=writes, numeric_reservations=[[0xfbcf64,156],[0xfbbee0,144]],
                  immutable_fast_name_ids=fast_names,
                  runtime='NOT_RUN: exact rebuilt output requires independent runtime QA')
    (out / 'SMALL_RUNTIME_BUILD.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    return bytes(result), report
