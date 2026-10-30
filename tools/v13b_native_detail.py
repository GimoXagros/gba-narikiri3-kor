"""Share one bounded tile-cache context during native monster detail drawing."""
import hashlib
import struct
import subprocess
from pathlib import Path


def apply(base, toolchain, out):
    if len(base) != 16777216 or base[0xcddf8:0xcde00].hex() != 'f0b557464e464546':
        raise ValueError('Native detail caller identity changed')
    if base[0xfbcb40:0xfbcb9c] != b'\xff'*92:
        raise ValueError('Native detail helper overlaps occupied data')
    out.mkdir(parents=True, exist_ok=False)
    def run(tool, args):
        subprocess.run([str(toolchain/('arm-none-eabi-'+tool+'.exe')), *map(str, args)],
                       check=True, capture_output=True)
    source = Path(__file__).resolve().parents[1]/'source/v13b/native_context.s'
    run('as', ['-mcpu=arm7tdmi', source, '-o', out/'code.o'])
    run('ld', ['-Ttext=0x08fbcb40', '-e', 'first', out/'code.o', '-o', out/'code.elf'])
    run('objcopy', ['-O', 'binary', '--only-section=.text', out/'code.elf', out/'code.bin'])
    code = (out/'code.bin').read_bytes()
    if len(code) != 92 or hashlib.sha256(code).hexdigest() != '945b9ac2847136733095ea8b848ce38d154ce867305ffe829e4f3c0a7af687dd':
        raise ValueError('Reviewed native detail helper changed')
    result = bytearray(base)
    result[0xfbcb40:0xfbcb9c] = code
    result[0xcddf8:0xcde00] = bytes.fromhex('004b1847') + struct.pack('<I', 0x08fbcb41)
    return bytes(result), dict(code_offset=0xfbcb40, code_bytes=92, hook_offset=0xcddf8,
                               stack_bytes=64, code_sha256=hashlib.sha256(code).hexdigest())
