"""Draw the verified encyclopedia number column without the generic formatter."""
import hashlib
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def apply(base, toolchain, out):
    if len(base) != 16777216 or base[0xccb80:0xccb88].hex() != '00b50a1c092a05dc':
        raise ValueError('Native numeric entry identity changed')
    regions = [('guard', 0xfbcf64, 156, 144), ('draw', 0xfbbee0, 144, 124)]
    for _, at, capacity, _ in regions:
        if base[at:at+capacity] != b'\xff'*capacity:
            raise ValueError('Numeric code must use its source-reserved empty slots')
    out.mkdir(parents=True, exist_ok=False)

    def run(tool, args):
        subprocess.run([str(toolchain/('arm-none-eabi-'+tool+'.exe')), *map(str, args)],
                       check=True, capture_output=True)

    run('as', ['-mcpu=arm7tdmi', ROOT/'source/v13b/numeric_prefix.s', '-o', out/'code.o'])
    run('ld', ['-T', ROOT/'source/v13b/numeric_prefix.ld', out/'code.o', '-o', out/'code.elf'])
    result = bytearray(base)
    writes = []

    def write(at, data):
        writes.append(dict(offset=at, expected_hex=base[at:at+len(data)].hex(),
                           payload_hex=data.hex()))
        result[at:at+len(data)] = data

    for name, at, _, size in regions:
        path = out/(name+'.bin')
        run('objcopy', ['-O', 'binary', '--only-section=.'+name, out/'code.elf', path])
        payload = path.read_bytes()
        if len(payload) != size:
            raise ValueError('Reviewed numeric code extent changed')
        write(at, payload)
    write(0xccb80, bytes.fromhex('004b1847')+struct.pack('<I', 0x08fbcf65))
    return bytes(result), dict(writes=writes, code_bytes=268,
                              candidate_sha256=hashlib.sha256(result).hexdigest(),
                              scope='Caller CD7F7, entries 1..154, exact normal column descriptor; otherwise original entry',
                              preserved='Digit tiles, cursor, dirty flag, formatter scratch and callee ABI')
