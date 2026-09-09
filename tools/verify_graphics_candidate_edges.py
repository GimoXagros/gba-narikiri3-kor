"""Prove scoped false pointer edges in compressed graphics, without ROM edits."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from verify_small_consumer import Fixture

ROOT = Path(__file__).resolve().parents[1]


def decode_stream(raw):
    """Bounded GBA LZ77 decoder, retaining each encoded byte's role.

    Same stream format used by the permitted ND2 reference decoder, with
    strict bank bounds and byte-role tracking added for this classification.
    """
    if len(raw) < 4 or raw[0] != 0x10:
        raise ValueError('Not a GBA LZ77 stream')
    size = int.from_bytes(raw[1:4], 'little')
    if not 0 < size <= 0x18000:
        raise ValueError('Graphics output outside GBA VRAM capacity')
    out = bytearray()
    roles = ['header'] * 4
    at = 4
    while len(out) < size:
        flags = raw[at]
        at += 1
        roles.append('flags')
        for bit in range(7, -1, -1):
            if len(out) == size:
                break
            if flags & (1 << bit):
                first, second = raw[at:at + 2]
                at += 2
                roles.extend(['back_reference_high', 'back_reference_low'])
                length = (first >> 4) + 3
                distance = ((first & 15) << 8 | second) + 1
                if distance > len(out):
                    raise ValueError('LZ reference precedes decoded output')
                for _ in range(min(length, size - len(out))):
                    out.append(out[-distance])
            else:
                out.append(raw[at])
                at += 1
                roles.append('literal')
    return bytes(out), at, roles


def verify(rom, profile):
    for guard in profile['guards']:
        at = int(guard['offset'], 0)
        raw = bytes.fromhex(guard['hex'])
        if rom[at:at + len(raw)] != raw:
            raise ValueError('Graphics consumer guard differs')
    rows = []
    for row in profile['banks']:
        bank, start, limit, edge = (int(row[k], 0) for k in ('bank', 'start', 'limit', 'edge'))
        if rom[bank:start] != bytes.fromhex(row['header_hex']):
            raise ValueError('Graphics bank directory differs')
        data, used, roles = decode_stream(rom[start:limit])
        if used != row['encoded_bytes'] or len(data) != row['decoded_bytes']:
            raise ValueError('Graphics stream extent differs')
        if hashlib.sha256(rom[start:start + used]).hexdigest() != row['encoded_sha256'] or hashlib.sha256(data).hexdigest() != row['decoded_sha256']:
            raise ValueError('Graphics encoded/decoded bytes changed')
        if not start + 4 <= edge < edge + 4 <= start + used or struct.unpack_from('<I', rom, edge)[0] != int(row['word'], 0):
            raise ValueError('Candidate no longer lies inside the encoded stream')
        f = Fixture(rom, 0)
        u = f.uc
        context = 0x02010000
        u.mem_write(0x0200337c, struct.pack('<I', context))
        events = []
        def hook(uc, address, size, _):
            if address == 0x08003444:
                events.append(['bank_lookup', uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)])
            elif address == 0x080dd440:
                events.append(['bios_lz77_vram', uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)])
                uc.emu_stop()
        u.hook_add(UC_HOOK_CODE, hook)
        u.reg_write(UC_ARM_REG_SP, 0x03007e00)
        u.reg_write(UC_ARM_REG_LR, 0x0203fff1)
        u.reg_write(UC_ARM_REG_R0, 0)
        u.emu_start(0x08000001 + int(row['code_entry'], 0), 0x0203fff0, count=100000)
        want = [['bank_lookup', 0x08000000 + bank, 0], ['bios_lz77_vram', 0x08000000 + start, 0x06000000]]
        if events != want or u.reg_read(UC_ARM_REG_PC) != 0x080dd440:
            raise ValueError(f'Original graphics loader route differs: {events}')
        rows.append({'edge': row['edge'], 'pointer_shaped_word': row['word'], 'stream': row['start'], 'encoded_byte_roles': roles[edge-start:edge-start+4], 'encoded_bytes': used, 'decoded_bytes': len(data), 'actual_cpu_route': events})
    return {'status': 'SCOPED_GRAPHICS_EDGE_CLASSIFICATION_PASS', 'rom_sha256': hashlib.sha256(rom).hexdigest(), 'false_pointer_edges': rows, 'scope': 'Original field caller -> B076C -> B06A4 -> 3444 -> 33F4 -> BIOS LZ77 VRAM entry, stopped before BIOS. Stream decoding independently checks exact bounded bytes. Synthetic context only, no normal gameplay claim. Only these two pointer-shaped words are classified; other references to their target strings are not excluded.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    profile = json.loads((ROOT / 'source/graphics_candidate_edge_profile.json').read_text(encoding='utf-8'))
    result = verify(args.rom.read_bytes(), profile)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
