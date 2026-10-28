"""Reclaim consent bitplane storage without changing its displayed pixels."""
import hashlib
import struct
import subprocess
from pathlib import Path
from intro_graphics_stage import optimal_rle
from gba_rle import unpack

ROOT = Path(__file__).resolve().parents[1]


def apply_boot(base, toolchain, out):
    if len(base) != 16777216:
        raise ValueError('Exact 16 MiB input required')
    packed = base[0xfbb600:0xfbbf70] + base[0xfbc3dc:0xfbcd2c]
    raw = b''.join(struct.pack('<H', 0x7fff if value >> bit & 1 else 0)
                   for value in packed for bit in range(8))
    if hashlib.sha256(raw).hexdigest() != '82773ec065898089374f4e7834a1d8e83adb8e5be8f5ebbc91dd0bd742e52a75':
        raise ValueError('Consent bitplane identity mismatch')
    # 08000240 initializes DMA3 to clear all 256 KiB of EWRAM.
    if (base[0x250:0x262].hex() != '3b4869460160802189044160394981608168'
            or base[0x340:0x348].hex() != 'd400000400000185'):
        raise ValueError('Boot scratch lifetime guard changed')
    blob = optimal_rle(packed)
    if unpack(blob, 0, len(blob), 4800)[0] != packed or len(blob) > 2416:
        raise ValueError('Boot compression roundtrip or capacity')
    out.mkdir(parents=True, exist_ok=False)
    def run(tool, args):
        subprocess.run([str(toolchain / ('arm-none-eabi-' + tool + '.exe')),
                        *map(str, args)], check=True, capture_output=True)
    run('as', ['-mcpu=arm7tdmi', ROOT/'source/v13b/boot_rle.s', '-o', out/'boot.o'])
    run('ld', ['-Ttext=0x08fbcd2c', '-e', 'boot_rle', out/'boot.o', '-o', out/'boot.elf'])
    run('objcopy', ['-O', 'binary', '--only-section=.text', out/'boot.elf', out/'boot.bin'])
    code = (out/'boot.bin').read_bytes()
    if len(code) != 44:
        raise ValueError('Boot stub extent changed')
    result = bytearray(base)
    result[0xfbb600:0xfbbf70] = blob + b'\xff'*(2416-len(blob))
    result[0xfbc3dc:0xfbcd2c] = b'\xff'*2384
    result[0xfbcd2c:0xfbcd6c] = code + b'\xff'*(64-len(code))
    return bytes(result), {'compressed_bytes': len(blob), 'stub_bytes': len(code),
                           'scratch': '02000000..020012C0', 'reclaimed': 'FBC3DC..FBCD2C'}
